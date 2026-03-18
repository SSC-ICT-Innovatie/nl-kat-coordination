from pathlib import Path
from unittest import mock

import boefjes.api
from boefjes.dependencies.plugins import PluginService
from boefjes.worker.interfaces import TaskStatus, WorkerManager
from boefjes.worker.repository import get_local_repository
from tests.conftest import MockSchedulerClient
from tests.loading import get_dummy_data


def _mocked_scheduler_client(tmp_path: Path):
    return MockSchedulerClient(
        boefje_responses=[get_dummy_data("scheduler/pop_response_boefje_no_ooi.json")],
        normalizer_responses=[],
        log_path=tmp_path / "patch_task_log",
    )


def test_healthz(api):
    response = api.get("/healthz")
    assert response.status_code == 200
    assert response.text == '"OK"'


def test_boefje_input_running(api, tmp_path):
    scheduler_client = _mocked_scheduler_client(tmp_path)
    tasks = scheduler_client.pop_items(WorkerManager.Queue("boefje"))
    scheduler_client.patch_task(tasks[0].id, TaskStatus.RUNNING)
    api.app.dependency_overrides[boefjes.api.get_scheduler_client] = lambda: scheduler_client
    api.app.dependency_overrides[boefjes.api.get_plugin_service] = lambda: PluginService(
        mock.MagicMock(), mock.MagicMock(), get_local_repository()
    )

    boefjes.api.get_environment_settings = lambda *_: {}
    response = api.get("/api/v0/tasks/70da7d4f-f41f-4940-901b-d98a92e9014b")
    assert response.status_code == 200
    assert response.json() == {
        "output_url": "http://placeholder:8006/api/v0/tasks/70da7d4f-f41f-4940-901b-d98a92e9014b",
        "task": {
            "id": "70da7d4f-f41f-4940-901b-d98a92e9014b",
            "scheduler_id": "boefje",
            "schedule_id": None,
            "organisation": "_dev",
            "priority": 1,
            "status": "running",
            "type": "boefje",
            "hash": "70da7d4f-f41f-4940-901b-d98a92e9014b",
            "data": {
                "id": "70da7d4f-f41f-4940-901b-d98a92e9014b",
                "started_at": None,
                "ended_at": None,
                "boefje": {"id": "dns-records", "version": None, "oci_image": None},
                "input_ooi": "",
                "arguments": {},
                "organization": "_dev",
                "runnable_hash": None,
                "environment": None,
            },
            "created_at": "2021-06-29T14:00:00",
            "modified_at": "2021-06-29T14:00:00",
        },
    }


def test_boefje_input_not_running(api, tmp_path):
    scheduler_client = _mocked_scheduler_client(tmp_path)
    scheduler_client.pop_items(WorkerManager.Queue("boefje"))
    api.app.dependency_overrides[boefjes.api.get_scheduler_client] = lambda: scheduler_client

    response = api.get("/api/v0/tasks/70da7d4f-f41f-4940-901b-d98a92e9014b")
    assert response.status_code == 403
