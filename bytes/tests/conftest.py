import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import alembic.config
import pytest
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from bytes.config import Settings
from bytes.database.db import SQL_BASE, get_engine
from bytes.database.sql_meta_repository import SQLMetaDataRepository
from bytes.rabbitmq import RabbitMQEventManager
from bytes.raw.file_raw_repository import FileRawRepository
from bytes.raw.middleware import IdentityMiddleware, NaclBoxMiddleware
from bytes.repositories.hash_repository import HashRepository
from bytes.timestamping.in_memory import InMemoryHashRepository
from bytes.timestamping.pastebin import PastebinHashRepository
from bytes.timestamping.rfc3161 import RFC3161HashRepository
from tests.client import BytesAPIClient


@pytest.fixture
def settings(tmpdir):
    env_path = Path(__file__).parent.parent / ".ci" / ".env.test"
    try:
        return Settings(data_dir=Path(tmpdir))
    except ValidationError:  # test is probably being run outside the container setup
        with env_path.open() as f:
            lines = [
                line.strip().split("=")
                for line in f.readlines()
                if line.strip() and line.strip()[-1] != "=" and not line.startswith("#")
            ]

            for key, val in lines:
                os.environ[key] = val

        return Settings(data_dir=Path(tmpdir), _env_file=env_path)


@pytest.fixture
def test_client(settings: Settings) -> TestClient:
    from bytes.api import app  # import creates a Settings object requiring proper env variables

    return TestClient(app)


@pytest.fixture
def nacl_middleware(settings: Settings) -> NaclBoxMiddleware:
    return NaclBoxMiddleware(kat_private=settings.private_key_b64, vws_public=settings.public_key_b64)


@pytest.fixture
def pastebin_hash_repository(settings: Settings) -> HashRepository:
    return PastebinHashRepository(api_dev_key=settings.pastebin_api_dev_key)


@pytest.fixture
def mock_hash_repository(settings: Settings) -> HashRepository:
    if settings.rfc3161_cert_file and settings.rfc3161_provider:
        return RFC3161HashRepository(settings.rfc3161_cert_file.read_bytes(), str(settings.rfc3161_provider))

    return InMemoryHashRepository(signing_provider_url="https://test")


@pytest.fixture
def meta_repository(
    raw_repository: FileRawRepository, mock_hash_repository: PastebinHashRepository, settings: Settings
) -> Iterator[SQLMetaDataRepository]:
    alembicArgs = ["--config", "/app/bytes/bytes/alembic.ini", "--raiseerr", "upgrade", "head"]
    alembic.config.main(argv=alembicArgs)

    engine = get_engine(db_uri=str(settings.db_uri), pool_size=settings.db_connection_pool_size)
    session = sessionmaker(bind=engine)()

    yield SQLMetaDataRepository(session, raw_repository, mock_hash_repository, settings)

    session.commit()

    sessionmaker(bind=engine, autocommit=True)().execute(
        ";".join([f"TRUNCATE TABLE {t} CASCADE" for t in SQL_BASE.metadata.tables])
    )


@pytest.fixture
def bytes_api_client(settings) -> Iterator[BytesAPIClient]:
    alembicArgs = ["--config", "/app/bytes/bytes/alembic.ini", "--raiseerr", "upgrade", "head"]
    alembic.config.main(argv=alembicArgs)

    client = BytesAPIClient("http://ci_bytes:8000", settings.username, settings.password)
    client.login()

    yield client

    sessionmaker(
        bind=get_engine(str(settings.db_uri), pool_size=settings.db_connection_pool_size), autocommit=True
    )().execute(";".join([f"TRUNCATE TABLE {t} CASCADE" for t in SQL_BASE.metadata.tables]))


@pytest.fixture
def raw_repository(tmp_path: Path) -> FileRawRepository:
    return FileRawRepository(tmp_path, IdentityMiddleware())


@pytest.fixture
async def event_manager(settings: Settings) -> AsyncIterator[RabbitMQEventManager]:
    manager = RabbitMQEventManager(str(settings.queue_uri))
    channel = await manager._get_channel()
    await channel.queue_delete("raw_file_received")

    yield manager
