from os import environ

from boefjes.worker.job_models import BoefjeMeta


def run(boefje_meta: BoefjeMeta) -> list[tuple[set, bytes | str]]:
    return [(set(), repr(dict(environ)).encode())]
