import logging
from ipaddress import ip_address
from os import getenv

import docker
from docker.errors import APIError
from requests.exceptions import RequestException

from boefjes.plugins.helpers import get_file_from_container

SSL_TEST_IMAGE = "drwetter/testssl.sh:3.2"


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    ip_port = input_["ip_port"]["port"]
    address = input_["ip_port"]["address"]["address"]

    if ip_address(address).version == 6:
        args = f" --jsonfile tmp/output.json --server-preference -6 [{address}]:{ip_port}"
    else:
        args = f" --jsonfile tmp/output.json --server-preference {address}:{ip_port}"

    timeout = getenv("TIMEOUT", 30)

    environment_vars = {"OPENSSL_TIMEOUT": timeout, "CONNECT_TIMEOUT": timeout}

    client = docker.from_env()
    container = client.containers.run(SSL_TEST_IMAGE, args, detach=True, environment=environment_vars)

    try:
        container.wait(timeout=300)
        output = get_file_from_container(container, "tmp/output.json")
    except (APIError, RequestException) as e:
        logging.warning("DockerException occurred: %s", e)
        container.stop()
        raise Exception("Error occurred (possibly a timeout) while running testssl.sh")
    finally:
        container.remove()

    if not output:
        raise Exception("Couldn't get tmp/output.json from testsll container")

    return [(set(), output)]
