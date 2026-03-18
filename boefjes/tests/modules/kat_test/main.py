from boefjes.worker.job_models import BoefjeMeta


def run(boefje_meta: BoefjeMeta) -> list[tuple[set, bytes | str]]:
    return [(set(), b"dummy-data")]
