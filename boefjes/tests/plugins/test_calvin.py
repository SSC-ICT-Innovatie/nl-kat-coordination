from boefjes.worker.job_models import NormalizerMeta
from octopoes.models.ooi.monitoring import Application
from tests.loading import get_dummy_data


def test_parse_user_changed(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("calvin-normalizer.json"))
    output = normalizer_runner.run(meta, get_dummy_data("user-changed.json"))

    assert len(output.declarations) == 8
    assert output.declarations[1].ooi.dict() == {
        "application": Application(name="organisation/env/app").reference,
        "event_id": '{"client_environment_app":"organisation/env/app","log_user_user_id":1234}-1655979300000',
        "event_title": "UC: User privilege monitoring",
        "event_type": "ksql-usecase",
        "meta_data": {
            "_id": "62b43a6e69c14474a3773f8b",
            "log_action_code": "U",
            "log_count": 9.0,
            "log_routing_key": "test_app.account_change",
            "log_user_user_id": 1234.0,
            "outbox_sent": None,
            "windowKey": '{"client_environment_app":"organisation/env/app","log_user_user_id":1234}-1655979300000',
            "window_emit": 1655978930000.0,
            "window_end": 1655979300000.0,
            "window_start": 1655975700000.0,
        },
        "object_type": "Incident",
        "primary_key": 'Incident|organisation/env/app|{"client_environment_app":"organisation/env/app",'
        '"log_user_user_id":1234}-1655979300000',
        "scan_profile": None,
        "user_id": None,
        "severity": "MEDIUM",
    }

    assert output.declarations[-1].ooi.dict() == {
        "application": Application(name="organisation/env/app").reference,
        "event_id": '{"client_environment_app":"organisation/env/app","log_user_user_id":1234}-1658825100000',
        "event_title": "UC: User privilege monitoring",
        "event_type": "ksql-usecase",
        "meta_data": {
            "_id": "62df9e499dd2b029d842576d",
            "log_action_code": "U",
            "log_count": 4.0,
            "log_routing_key": "test_app.account_change",
            "log_user_user_id": 1234.0,
            "outbox_sent": None,
            "windowKey": '{"client_environment_app":"organisation/env/app","log_user_user_id":1234}-1658825100000',
            "window_emit": 1658822215000.0,
            "window_end": 1658825100000.0,
            "window_start": 1658821500000.0,
        },
        "object_type": "Incident",
        "primary_key": 'Incident|organisation/env/app|{"client_environment_app":"organisation/env/app",'
        '"log_user_user_id":1234}-1658825100000',
        "scan_profile": None,
        "user_id": None,
        "severity": "MEDIUM",
    }


def test_parse_admin_login_failure(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("calvin-normalizer.json"))
    output = normalizer_runner.run(meta, get_dummy_data("user-login-admin-failure.json"))

    assert len(output.declarations) == 8
    assert output.declarations[1].ooi.dict() == {
        "application": Application(name="organisation/env/app").reference,
        "event_id": '{"client_environment_app":"organisation/env/app","log_user_user_id":1234}-1659618600000',
        "event_title": "UC: Detect brute force login attempts for an admin account",
        "event_type": "ksql-usecase",
        "meta_data": {
            "_id": "62ebc44c9dd2b029d84ac32a",
            "log_action_code": "E",
            "log_count": 3.0,
            "log_object_result": 0.0,
            "log_routing_key": "test_app.user_login",
            "log_user_roles": "ADMIN,REGISTRATOR,SHIFT_MANAGER,CSV,KVTB_ADMIN,STATS",
            "log_user_user_id": 1234.0,
            "outbox_sent": True,
            "windowKey": '{"client_environment_app":"organisation/env/app","log_user_user_id":1234}-1659618600000',
            "window_emit": 1659618378000.0,
            "window_end": 1659618600000.0,
            "window_start": 1659617700000.0,
        },
        "object_type": "Incident",
        "primary_key": 'Incident|organisation/env/app|{"client_environment_app":"organisation/env/app",'
        '"log_user_user_id":1234}-1659618600000',
        "scan_profile": None,
        "user_id": None,
        "severity": "MEDIUM",
    }


def test_parse_user_login_failure(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("calvin-normalizer.json"))
    output = normalizer_runner.run(meta, get_dummy_data("user-login-failure.json"))

    assert len(output.declarations) == 8
    assert output.declarations[1].ooi.dict() == {
        "application": Application(name="organisation/env/app").reference,
        "event_id": '{"client_environment_app":"organisation/env/app","log_user_user_id":1234}-1658998200000',
        "event_title": "UC: Detects attempts to guess passwords",
        "event_type": "ksql-usecase",
        "meta_data": {
            "_id": "62e24d509dd2b029d84391fb",
            "log_action_code": "E",
            "log_count": 10.0,
            "log_object_result": 0.0,
            "log_object_user_id": None,
            "log_result": None,
            "log_routing_key": "test_app.user_login",
            "log_user_user_id": 1234.0,
            "outbox_sent": None,
            "windowKey": '{"client_environment_app":"organisation/env/app","log_user_user_id":1234}-1658998200000',
            "window_emit": 1658998093000.0,
            "window_end": 1658998200000.0,
            "window_start": 1658996400000.0,
        },
        "object_type": "Incident",
        "primary_key": 'Incident|organisation/env/app|{"client_environment_app":"organisation/env/app",'
        '"log_user_user_id":1234}-1658998200000',
        "scan_profile": None,
        "user_id": None,
        "severity": "MEDIUM",
    }
