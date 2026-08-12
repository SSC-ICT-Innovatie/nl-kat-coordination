import json
import os
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from boefjes.config import Settings
from boefjes.job_handler import LocalNormalizerHandler
from boefjes.worker.interfaces import Task, TaskStatus
from boefjes.worker.job_models import NormalizerMeta
from octopoes.models import DeclaredScanProfile
from tests.loading import get_dummy_data

RAW_DATA = json.dumps(
    {"ip_addresses": [{"address": "127.0.0.1"}, {"address": "10.0.0.0"}], "domains": [{"name": "example.com"}]}
)


def test_normalizer_can_yield_scan_profiles(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("external_db.json"))
    output = normalizer_runner.run(meta, bytes(RAW_DATA, "UTF-8"))

    assert len(output.observations) == 1
    assert len(output.observations[0].results) == 3
    assert len(output.scan_profiles) == 3

    profile = output.scan_profiles[0]
    assert isinstance(profile, DeclaredScanProfile)
    assert profile.reference == "IPAddressV4|internet|127.0.0.1"
    assert profile.level == 3

    profile = output.scan_profiles[1]
    assert isinstance(profile, DeclaredScanProfile)
    assert profile.reference == "IPAddressV4|internet|10.0.0.0"
    assert profile.level == 3

    profile = output.scan_profiles[2]
    assert isinstance(profile, DeclaredScanProfile)
    assert profile.reference == "Hostname|internet|example.com"
    assert profile.level == 3


def test_job_handler_respects_whitelist(normalizer_runner, mocker):
    bytes_mock = mocker.Mock()
    bytes_mock.get_raw.return_value = RAW_DATA
    octopoes = mocker.Mock()

    meta = NormalizerMeta.model_validate_json(get_dummy_data("external_db.json"))
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
        data=meta,
    )
    os.environ["BOEFJES_SCAN_PROFILE_WHITELIST"] = '{"x": 5}'
    with pytest.raises(ValidationError):
        Settings()

    os.environ["BOEFJES_SCAN_PROFILE_WHITELIST"] = '{"x": -1}'
    with pytest.raises(ValidationError):
        Settings()

    os.environ["BOEFJES_SCAN_PROFILE_WHITELIST"] = '{"x": 3}'
    LocalNormalizerHandler(normalizer_runner, bytes_mock, Settings().scan_profile_whitelist, lambda x: octopoes).handle(
        task
    )
    assert octopoes.save_many_scan_profiles.call_count == 0

    os.environ["BOEFJES_SCAN_PROFILE_WHITELIST"] = '{"kat_external_db_normalize": 2}'
    LocalNormalizerHandler(normalizer_runner, bytes_mock, Settings().scan_profile_whitelist, lambda x: octopoes).handle(
        task
    )
    assert octopoes.save_many_scan_profiles.call_count == 1
    assert octopoes.save_many_scan_profiles.call_args[0][0][0].level == 2

    os.environ["BOEFJES_SCAN_PROFILE_WHITELIST"] = '{"kat_external_db_normalize": 3}'
    LocalNormalizerHandler(normalizer_runner, bytes_mock, Settings().scan_profile_whitelist, lambda x: octopoes).handle(
        task
    )
    assert octopoes.save_many_scan_profiles.call_count == 2
    assert octopoes.save_many_scan_profiles.call_args[0][0][0].level == 3

    os.environ["BOEFJES_SCAN_PROFILE_WHITELIST"] = '{"kat_external_db_normalize": 4, "abc": 0}'
    LocalNormalizerHandler(normalizer_runner, bytes_mock, Settings().scan_profile_whitelist, lambda x: octopoes).handle(
        task
    )
    assert octopoes.save_many_scan_profiles.call_count == 3
