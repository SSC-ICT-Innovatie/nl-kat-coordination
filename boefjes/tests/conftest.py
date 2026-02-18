import base64
import multiprocessing
import time
import uuid
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import alembic.config
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy.orm import sessionmaker

from boefjes.clients.bytes_client import BytesAPIClient
from boefjes.config import settings
from boefjes.dependencies.plugins import PluginService, get_plugin_service
from boefjes.job_handler import NormalizerHandler, bytes_api_client
from boefjes.katalogus.root import app
from boefjes.local.runner import LocalNormalizerJobRunner
from boefjes.sql.config_storage import SQLConfigStorage, create_encrypter
from boefjes.sql.db import SQL_BASE, get_engine
from boefjes.sql.organisation_storage import SQLOrganisationStorage, get_organisations_store
from boefjes.sql.plugin_storage import SQLPluginStorage
from boefjes.storage.interfaces import OrganisationNotFound
from boefjes.storage.memory import ConfigStorageMemory, OrganisationStorageMemory, PluginStorageMemory
from boefjes.worker.boefje_handler import LocalBoefjeHandler, _copy_raw_files
from boefjes.worker.interfaces import (
    BoefjeHandler,
    BoefjeOutput,
    BoefjeStorageInterface,
    File,
    SchedulerClientInterface,
    StatusEnum,
    Task,
    TaskPop,
    TaskStatus,
    WorkerManager,
)
from boefjes.worker.job_models import BoefjeMeta, NormalizerMeta
from boefjes.worker.manager import SchedulerWorkerManager
from boefjes.worker.models import Organisation
from boefjes.worker.repository import (
    LocalPluginRepository,
    _cached_resolve_boefjes,
    _cached_resolve_normalizers,
    get_boefje_resource,
    get_local_repository,
    get_normalizer_resource,
)
from octopoes.api.models import Declaration, Observation
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network
from octopoes.models.ooi.service import IPService, Service
from tests.loading import get_dummy_data


class MockSchedulerClient(SchedulerClientInterface):
    def __init__(
        self,
        boefje_responses: list[bytes],
        normalizer_responses: list[bytes],
        log_path: Path,
        raise_on_empty_queue: Exception = KeyboardInterrupt,
        iterations_to_wait_for_exception: int = 0,
        sleep_time: float = 0.1,
    ):
        self.boefje_responses = boefje_responses
        self.normalizer_responses = normalizer_responses

        log_path.touch(exist_ok=True)
        self.log_path = log_path
        self.raise_on_empty_queue = raise_on_empty_queue
        self.iterations_to_wait_for_exception = iterations_to_wait_for_exception
        self.sleep_time = sleep_time

        self._iterations = 0
        self._tasks: dict[str, list[Task]] = multiprocessing.Manager().dict()
        self._popped_items: dict[str, list[Task]] = multiprocessing.Manager().dict()
        self._pushed_items: dict[str, list[Task]] = multiprocessing.Manager().dict()

    def pop_items(
        self, queue: WorkerManager.Queue, filters: dict[str, list[dict[str, Any]]] | None = None, limit: int | None = 1
    ) -> list[Task]:
        time.sleep(self.sleep_time)

        try:
            if queue is WorkerManager.Queue.BOEFJES:
                response = TypeAdapter(TaskPop).validate_json(self.boefje_responses.pop(0))
            elif queue is WorkerManager.Queue.NORMALIZERS:
                response = TypeAdapter(TaskPop).validate_json(self.normalizer_responses.pop(0))
            else:
                return []

            p_items = response.results

            for p_item in p_items:
                self._popped_items[str(p_item.id)] = p_item
                self._tasks[str(p_item.id)] = self._task_from_id(p_item.id)

            return p_items

        except IndexError:
            time.sleep(3 * self.sleep_time)
            raise self.raise_on_empty_queue

    def patch_task(self, task_id: UUID, status: TaskStatus) -> None:
        with self.log_path.open("a") as f:
            f.write(f"{task_id},{status.value}\n")

        task = self._task_from_id(task_id) if str(task_id) not in self._tasks else self._tasks[str(task_id)]
        task.status = status
        self._tasks[str(task_id)] = task

    def get_all_patched_tasks(self) -> list[tuple[str, ...]]:
        with self.log_path.open() as f:
            return [tuple(x.strip().split(",")) for x in f]

    def get_task(self, task_id: UUID, hydrate: bool = True) -> Task:
        return self._task_from_id(task_id) if str(task_id) not in self._tasks else self._tasks[str(task_id)]

    def _task_from_id(self, task_id: UUID):
        return self._popped_items[str(task_id)]

    def push_item(self, p_item: Task) -> None:
        self._pushed_items[str(p_item.id)] = [p_item]


class MockBytesAPIClient(BoefjeStorageInterface):
    def __init__(self):
        self.queue = multiprocessing.Manager().Queue()

    def save_output(self, boefje_meta: BoefjeMeta, boefje_output: BoefjeOutput) -> dict[str, uuid.UUID]:
        self.save_boefje_meta(boefje_meta)

        return self.save_raws(boefje_meta.id, boefje_output)

    def save_boefje_meta(self, boefje_meta: BoefjeMeta) -> None:
        self.queue.put(("save_boefje_meta", (boefje_meta.model_dump(),)))

    def save_raws(self, boefje_meta_id: uuid.UUID, boefje_output: BoefjeOutput) -> dict[str, uuid.UUID]:
        self.queue.put(("save_raw", (boefje_meta_id, boefje_output)))

        return {file.name: uuid.uuid4() for file in boefje_output.files}

    def get_all(self) -> list[BoefjeMeta | NormalizerMeta]:
        return [self.queue.get() for _ in range(self.queue.qsize())]


class MockHandler(BoefjeHandler, NormalizerHandler):
    def __init__(self, exception=Exception):
        self.sleep_time = 0
        self.queue = multiprocessing.Manager().Queue()
        self.exception = exception
        self.boefje_storage = MockBytesAPIClient()

    def handle(self, task: Task) -> tuple[BoefjeMeta, BoefjeOutput] | None | Literal[False]:
        time.sleep(self.sleep_time)

        if str(task.id) in ["9071c9fd-2b9f-440f-a524-ef1ca4824fd4", "2071c9fd-2b9f-440f-a524-ef1ca4824fd4"]:
            time.sleep(self.sleep_time)
            raise self.exception()

        self.queue.put(task)

        if task.data.boefje.id == "docker":
            return False

        return task.data, BoefjeOutput(
            status=StatusEnum.COMPLETED,
            files=[File(name="1", content=base64.b64encode(b"123").decode(), tags={"my/mime"})],
        )

    def copy_raw_files(
        self, task: Task, output: tuple[BoefjeMeta, BoefjeOutput] | Literal[False], duplicated_tasks: list[Task]
    ) -> None:
        if output is False:
            return

        boefje_meta, boefje_output = output

        _copy_raw_files(self.boefje_storage, boefje_meta, boefje_output, duplicated_tasks)

    def get_all(self) -> list[Task]:
        return [self.queue.get() for _ in range(self.queue.qsize())]


@pytest.fixture(autouse=True)
def clear_caches():
    get_boefje_resource.cache_clear()
    get_normalizer_resource.cache_clear()
    _cached_resolve_boefjes.cache_clear()
    _cached_resolve_normalizers.cache_clear()


@pytest.fixture
def item_handler(tmp_path: Path):
    return MockHandler()


@pytest.fixture
def mock_boefje_handler(mock_local_repository: LocalPluginRepository, mocker):
    return LocalBoefjeHandler(mock_local_repository, mocker.MagicMock())


@pytest.fixture
def manager(item_handler: MockHandler, tmp_path: Path) -> SchedulerWorkerManager:
    scheduler_client = MockSchedulerClient(
        boefje_responses=[
            get_dummy_data("scheduler/pop_response_boefje.json"),
            get_dummy_data("scheduler/pop_response_boefje_2.json"),
            get_dummy_data("scheduler/should_crash.json"),
        ],
        normalizer_responses=[get_dummy_data("scheduler/pop_response_normalizer.json")],
        log_path=tmp_path / "patch_task_log",
    )

    return SchedulerWorkerManager(
        item_handler, scheduler_client, pool_size=1, poll_interval=0.01, worker_heartbeat=1.0, deduplicate=True
    )


@pytest.fixture
def api(tmp_path):
    from boefjes.api import app

    return TestClient(app)


@pytest.fixture
def session():
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "head"])
    engine = get_engine()
    session = sessionmaker(bind=engine)()

    yield session

    session.commit()
    engine.execute(";".join([f"TRUNCATE TABLE {t} CASCADE" for t in SQL_BASE.metadata.tables]))


@pytest.fixture
def organisation_storage(session):
    return SQLOrganisationStorage(session, settings)


@pytest.fixture
def config_storage(session):
    return SQLConfigStorage(session, create_encrypter())


@pytest.fixture
def plugin_storage(session):
    return SQLPluginStorage(session, settings)


@pytest.fixture
def local_repository():
    return get_local_repository()


@pytest.fixture
def mock_local_repository():
    return LocalPluginRepository(Path(__file__).parent / "modules")


@pytest.fixture
def normalizer_runner(local_repository: LocalPluginRepository):
    return LocalNormalizerJobRunner(local_repository)


@pytest.fixture
def mock_normalizer_runner(mock_local_repository: LocalPluginRepository):
    return LocalNormalizerJobRunner(mock_local_repository)


@pytest.fixture
def plugin_service(plugin_storage, config_storage, local_repository):
    return PluginService(plugin_storage, config_storage, local_repository)


@pytest.fixture
def test_organisation():
    return Organisation(id="test", name="Test org")


@pytest.fixture
def second_test_organisation():
    return Organisation(id="test2", name="Test org2")


@pytest.fixture
def mock_plugin_service(mock_local_repository, test_organisation) -> PluginService:
    storage = ConfigStorageMemory()
    storage.upsert(test_organisation.id, "test_plugin", {"DUMMY_VAR": "123"})

    return PluginService(PluginStorageMemory(), storage, mock_local_repository)


@pytest.fixture
def organisation(organisation_storage, test_organisation) -> Organisation:
    with organisation_storage as repo:
        repo.create(test_organisation)

    return test_organisation


@pytest.fixture
def second_organisation(organisation_storage, second_test_organisation) -> Organisation:
    with organisation_storage as repo:
        repo.create(second_test_organisation)

    return second_test_organisation


@pytest.fixture
def unit_test_client(mock_plugin_service) -> TestClient:
    client = TestClient(app)
    _store = OrganisationStorageMemory({"test": Organisation(id="test", name="Test")})

    services = {"test": mock_plugin_service}

    def get_service(organisation_id: str):
        if organisation_id in services:
            return services.get(organisation_id)

        raise OrganisationNotFound(organisation_id)

    app.dependency_overrides[get_organisations_store] = lambda: _store
    app.dependency_overrides[get_plugin_service] = get_service

    yield client

    app.dependency_overrides = {}


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def octopoes_api_connector(organisation) -> OctopoesAPIConnector:
    connector = OctopoesAPIConnector(str(settings.octopoes_api), organisation.id)
    connector.create_node()
    yield connector
    connector.delete_node()


@pytest.fixture
def bytes_client(request) -> BytesAPIClient:
    return bytes_api_client


@pytest.fixture
def valid_time():
    return datetime.now(timezone.utc)


def seed_system(
    octopoes_api_connector: OctopoesAPIConnector,
    valid_time: datetime,
    test_hostname: str = "example.com",
    test_ip: str = "192.0.2.3",
    test_ipv6: str = "3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230",
    method: str = "kat_nmap_normalize",
) -> dict[str, list[OOI]]:
    network = Network(name="test")
    octopoes_api_connector.save_declaration(Declaration(ooi=network, valid_time=valid_time))

    hostnames = [
        Hostname(network=network.reference, name=test_hostname),
        Hostname(network=network.reference, name=f"a.{test_hostname}"),
        Hostname(network=network.reference, name=f"b.{test_hostname}"),
        Hostname(network=network.reference, name=f"c.{test_hostname}"),
        Hostname(network=network.reference, name=f"d.{test_hostname}"),
        Hostname(network=network.reference, name=f"e.{test_hostname}"),
        Hostname(network=network.reference, name=f"f.{test_hostname}"),
    ]

    addresses = [
        IPAddressV4(network=network.reference, address=ip_address(test_ip)),
        IPAddressV6(network=network.reference, address=ip_address(test_ipv6)),
    ]
    ports = [
        IPPort(address=addresses[0].reference, protocol="tcp", port=25),
        IPPort(address=addresses[0].reference, protocol="tcp", port=443),
        IPPort(address=addresses[0].reference, protocol="tcp", port=22),
        IPPort(address=addresses[1].reference, protocol="tcp", port=80),
    ]
    services = [Service(name="smtp"), Service(name="https"), Service(name="http"), Service(name="ssh")]
    ip_services = [
        IPService(ip_port=ports[0].reference, service=services[0].reference),
        IPService(ip_port=ports[1].reference, service=services[1].reference),
        IPService(ip_port=ports[2].reference, service=services[3].reference),
        IPService(ip_port=ports[3].reference, service=services[2].reference),
    ]

    oois = hostnames + addresses + ports + services + ip_services

    octopoes_api_connector.save_observation(
        Observation(
            method=method,
            source_method=None,
            source=hostnames[0].reference,
            task_id=uuid.uuid4(),
            valid_time=valid_time,
            result=oois,
        )
    )
    octopoes_api_connector.recalculate_bits()

    return {
        "hostnames": hostnames,
        "addresses": addresses,
        "ports": ports,
        "services": services,
        "ip_services": ip_services,
    }
