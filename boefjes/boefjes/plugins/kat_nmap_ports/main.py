import re
from ipaddress import IPv6Address, ip_address
from os import getenv

import docker

NMAP_IMAGE = "instrumentisto/nmap:latest"
NMAP_VALID_PORTS = re.compile(
    "\\s*([TUSP]:)?(\\d+|[a-z*?]+|(\\[?\\d*-\\d*\\]?))(,(([TUSP]:)|\\s)?(\\d+|[a-z*?]+|(\\[?\\d*-\\d*\\]?)))*"
)


def run_nmap(args: list[str]) -> str:
    """Run Nmap in Docker."""
    client = docker.from_env()
    return client.containers.run(NMAP_IMAGE, args, remove=True).decode()


def build_nmap_arguments(host: str, ports: str | None) -> list[str]:
    """Build nmap arguments from the hosts IP with the required ports."""
    ip = ip_address(host)
    args = ["nmap", "-T4", "-Pn", "-r", "-v10", "-sV", "-sS", "-sU", f"-p{validate_ports(ports=ports)}"]
    if isinstance(ip, IPv6Address):
        args.append("-6")
    args.extend(["-oX", "-", host])

    return args


def validate_ports(ports: str | None) -> str:
    """Returns ports argument if valid. Double slashes are for flake8 W605.

    A valid port is:
    - a single port (set of digits) {22}
        - Regex: \\d+
    - a port range (optional digits separated by hyphen, optionally bracketed) {[80-]}
        - Regex: (\\[?\\d*-\\d*\\]?)
    - a valid Nmap protocol (alfanumeric wildcarded lowercase) {https*}
        - Regex: [a-z*?]+

    There needs to be at least one valid port. Multiple ports can be separated by a comma (',').
    A port can be preceded by 'T:', 'U:', 'S:' or 'P:' to specify a protocol
        - Regex: ([TUSP]:)?
    There can be spaces between the flag and its arguments.
        - Regex: \\s*

    Regex: "\\s*([TUSP]:)?(\\d+|[a-z*?]+|(\\[?\\d*-\\d*\\]?))(,(([TUSP]:)|\\s)?(\\d+|[a-z*?]+|(\\[?\\d*-\\d*\\]?)))*"

    See also: https://nmap.org/book/port-scanning-options.html.
    """
    if ports is None:
        raise ValueError('"PORTS" argument is not specified.')
    if NMAP_VALID_PORTS.fullmatch(ports) is None:
        raise ValueError(f'Invalid PORTS argument "{ports}"')
    return ports


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Build Nmap arguments and return results to normalizer."""
    return [
        (
            set(),
            run_nmap(build_nmap_arguments(host=boefje_meta["arguments"]["input"]["address"], ports=getenv("PORTS"))),
        )
    ]
