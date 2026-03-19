import base64
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from uuid import UUID

import pytest

from boefjes.worker.boefje_handler import LocalBoefjeHandler
from boefjes.worker.interfaces import StatusEnum, Task, TaskStatus
from boefjes.worker.job_models import BoefjeMeta, InvalidReturnValueNormalizer, NormalizerMeta
from boefjes.worker.models import Bit, Boefje, Normalizer, PluginType
from boefjes.worker.repository import LocalPluginRepository
from tests.loading import get_dummy_data, get_task

boefjes = [
    Boefje(id="test-boefje-1", name="test-boefje-1", consumes={"SomeOOI"}, produces=["test-boef-1", "test/text"]),
    Boefje(id="test-boefje-2", name="test-boefje-2", consumes={"SomeOOI"}, produces=["test-boef-2", "test/text"]),
    Boefje(id="test-boefje-3", name="test-boefje-3", consumes={"SomeOOI"}, produces=["test-boef-3", "test/plain"]),
    Boefje(id="test-boefje-4", name="test-boefje-4", consumes={"SomeOOI"}, produces=["test-boef-4", "test/and-simple"]),
]
normalizers = [
    Normalizer(
        id="test-normalizer-1",
        name="test-normalizer-1",
        consumes=["test-boef-3", "test/text"],
        produces=["SomeOOI", "OtherOOI"],
    ),
    Normalizer(id="test-normalizer-2", name="test-normalizer-2", consumes=["test/text"], produces=["SomeOtherOOI"]),
]
bits = [
    Bit(id="test-bit-1", name="test-bit-1", consumes="SomeOOI", produces=["SomeOOI"], parameters=[]),
    Bit(id="test-bit-2", name="test-bit-2", consumes="SomeOOI", produces=["SomeOOI", "SomeOtherOOI"], parameters=[]),
]
plugins: list[PluginType] = boefjes + normalizers + bits
sys.path.append(str(Path(__file__).parent))


def test_parse_normalizer_meta_to_json():
    meta = NormalizerMeta.model_validate_json(get_dummy_data("snyk-normalizer.json"))
    meta.started_at = datetime(10, 10, 10, 10, tzinfo=timezone.utc)
    meta.ended_at = datetime(10, 10, 10, 12, tzinfo=timezone.utc)

    assert "0010-10-10T10:00:00Z" in meta.model_dump_json()
    assert "0010-10-10T12:00:00Z" in meta.model_dump_json()


def test_handle_boefje_with_exception(mocker):
    mocker.patch("boefjes.clients.scheduler_client.get_environment_settings", return_value={})
    mock_bytes_api_client = mocker.patch("boefjes.job_handler.bytes_api_client")
    mocker.patch("boefjes.job_handler.get_octopoes_api_connector")

    task = Task(
        id=uuid.uuid4().hex,
        scheduler_id="test",
        schedule_id="test",
        organisation="test",
        priority=1,
        status=TaskStatus.RUNNING,
        type="boefje",
        created_at=datetime.now(),
        modified_at=datetime.now(),
        data=BoefjeMeta(
            id="0dca59db-b339-47c4-bcc9-896fc18e2386",
            boefje={"id": "dummy_boefje_runtime_exception"},
            input_ooi="Network|internet",
            arguments={},
            organization="_dev",
        ),
    )
    local_repository = LocalPluginRepository(Path(__file__).parent / "modules")

    mock_session = mock.MagicMock()
    mock_session.query.all.return_value = []

    with pytest.raises(RuntimeError):  # Bytes still saves exceptions before they are reraised
        LocalBoefjeHandler(local_repository, mock_bytes_api_client).handle(task)

    mock_bytes_api_client.save_output.assert_called_once()
    raw_call_args = mock_bytes_api_client.save_output.call_args

    assert raw_call_args[0][0].id == UUID("0dca59db-b339-47c4-bcc9-896fc18e2386")
    assert raw_call_args[0][1].status == StatusEnum.FAILED
    contents = base64.b64decode(raw_call_args[0][1].files[0].content).decode()
    assert "Traceback (most recent call last)" in contents
    assert "RuntimeError: dummy error" in contents
    # default mime-types are added through the API
    assert set(raw_call_args[0][1].files[0].tags) == {"error/boefje", "boefje/dummy_boefje_runtime_exception"}


def test_exception_raised_unsupported_return_type_normalizer(mock_normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("dns-normalize.json"))
    meta.raw_data.boefje_meta.input_ooi = None
    meta.normalizer.id = "dummy_bad_normalizer_return_type"

    with pytest.raises(InvalidReturnValueNormalizer):
        mock_normalizer_runner.run(meta, b"123")


def test_exception_raised_invalid_return_value(mock_normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("dns-normalize.json"))
    meta.raw_data.boefje_meta.input_ooi = None
    meta.normalizer.id = "dummy_bad_normalizer_dict_structure"

    with pytest.raises(InvalidReturnValueNormalizer):
        mock_normalizer_runner.run(meta, b"123")


def test_cleared_boefje_env(mock_boefje_handler) -> None:
    """This test checks if un-containerized (local) boefjes can only access their explicitly set env vars"""
    task = get_task(boefje_id="dummy_boefje_environment")
    task.data.environment = {"ARG1": "value1", "ARG2": "value2"}

    current_env = os.environ.copy()
    mock_boefje_handler.handle(task)

    # Assert that the original environment has been restored correctly
    assert current_env == os.environ


def test_correct_local_runner_hash(mock_local_repository) -> None:
    """This test checks if calculating the hash of local boefjes returns the correct result"""
    boefje_resource_1 = mock_local_repository.by_id("dummy_boefje_environment")
    boefje_resource_2 = mock_local_repository.by_id("dummy")

    # This boefje has a __pycache__ folder with *.pyc files, which should be ignored
    boefje_resource_3 = mock_local_repository.by_id("dummy_boefje_environment_with_pycache")

    # Sanity check to make sure the .pyc files are actually there
    path = Path(__file__).parent / "modules" / "dummy_boefje_environment_with_pycache"
    assert Path(path / "some_subdir/cache.pyc").is_file()
    assert Path(path / "some_subdir/__init__.py").is_file()
    assert Path(path / "__pycache__/pytest__init__.cpython-311.pyc").is_file()
    assert Path(path / "__pycache__/pytest_main.cpython-311.pyc").is_file()

    assert boefje_resource_1.boefje.runnable_hash == "7a6de035b9b3f3de1534582df3a1024476d62aad4fce51b7ffa9f13dd92dcbd2"
    assert boefje_resource_2.boefje.runnable_hash == "125d118d21c25ca522fc436cbe1ac8af336b7a973423d23ca02ce287a6c07b2d"
    assert boefje_resource_3.boefje.runnable_hash == "3fceaf2422bd6d3975e73d5d7d297e9c4a70efce60fccfab761235f08b6891b4"
