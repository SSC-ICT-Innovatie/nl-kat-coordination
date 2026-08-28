from boefjes.sql.db_models import RunOnDB
from boefjes.worker.models import RunOn


def test_run_on():
    assert RunOnDB.from_run_ons([RunOn.CREATE]) == RunOnDB.CREATE
    assert RunOnDB.from_run_ons([RunOn.UPDATE]) == RunOnDB.UPDATE
    assert RunOnDB.from_run_ons([RunOn.CREATE, RunOn.UPDATE]) == RunOnDB.CREATE_UPDATE
    assert RunOnDB.from_run_ons([RunOn.UPDATE, RunOn.CREATE]) == RunOnDB.CREATE_UPDATE
    assert RunOnDB.from_run_ons([1]) is None
    assert RunOnDB.from_run_ons([]) is None

    assert RunOnDB.CREATE.to_run_ons() == [RunOn.CREATE]
    assert RunOnDB.UPDATE.to_run_ons() == [RunOn.UPDATE]
    assert RunOnDB.CREATE_UPDATE.to_run_ons() == [RunOn.CREATE, RunOn.UPDATE]
