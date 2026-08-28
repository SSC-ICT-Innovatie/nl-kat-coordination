import docker

SSLSCAN_IMAGE = "breezethink/sslscan:latest"


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    client = docker.from_env()
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["hostname"]["name"]

    output = client.containers.run(SSLSCAN_IMAGE, ["--xml=-", hostname], remove=True)

    return [(set(), output)]
