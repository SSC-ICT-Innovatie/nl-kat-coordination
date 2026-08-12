import logging
import os
import re
import subprocess
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, _BaseAddress, ip_address, ip_network

TOP_PORTS_DEFAULT = 250
TOP_PORTS_UDP_DEFAULT = 250
TOP_PORTS_NETWORK_UDP_DEFAULT = 10
TOP_PORTS_MAX = 65535
TOP_PORTS_MIN = 1
NMAP_VALID_PORTS = re.compile(
    "\\s*([TUSP]:)?(\\d+|[a-z*?]+|(\\[?\\d*-\\d*\\]?))(,(([TUSP]:)|\\s)?(\\d+|[a-z*?]+|(\\[?\\d*-\\d*\\]?)))*"
)


class UnacceptedVSLM(Exception):
    pass


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


def parse_input_ooi(input_ooi: dict) -> IPv4Address | IPv6Address | IPv4Network | IPv6Network:
    if input_ooi["object_type"] == "IPAddressV4" or input_ooi["object_type"] == "IPAddressV6":
        return ip_address(input_ooi["address"])

    if input_ooi["object_type"] == "IPV4NetBlock" or input_ooi["object_type"] == "IPV6NetBlock":
        network = ip_network(f"{input_ooi['start_ip']['address']}/{str(input_ooi['mask'])}")
        min_mask = int(os.getenv("MIN_VLSM_IPV4", 22))

        if isinstance(network, IPv6Network):
            min_mask = int(os.getenv("MIN_VLSM_IPV6", 118))

        if network.prefixlen < min_mask:
            logging.info("Minimum expected VLSM %d > %d, skipping this range.", min_mask, network.prefixlen)
            raise UnacceptedVSLM("Skipping range due to unaccepted VSLM.")

        return network

    raise ValueError("Invalid OOI type")


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    try:
        input_ips = parse_input_ooi(boefje_meta["arguments"]["input"])
    except UnacceptedVSLM as e:
        return [({"info/boefje"}, str(e))]

    cmd = ["nmap"] + boefje_meta["arguments"]["oci_arguments"]

    if os.getenv("PORTS"):
        cmd.append(f"-p{validate_ports(ports=os.getenv('PORTS'))}")
    else:
        if "-sU" in cmd:  # I.e. we are doing an udp scan
            default = TOP_PORTS_UDP_DEFAULT if isinstance(input_ips, _BaseAddress) else TOP_PORTS_NETWORK_UDP_DEFAULT
            top_ports = int(os.getenv("TOP_PORTS_UDP", default))
        else:
            top_ports = int(os.getenv("TOP_PORTS", TOP_PORTS_DEFAULT))

        if not TOP_PORTS_MIN <= top_ports <= TOP_PORTS_MAX:
            raise ValueError(f"The value of top_ports is invalid: {top_ports}")

        cmd.extend(["--top-ports", str(top_ports)])

    if isinstance(input_ips, IPv6Address | IPv6Network):
        cmd.append("-6")

    cmd.extend(["-oX", "-", str(input_ips)])

    output = subprocess.run(cmd, capture_output=True)
    output.check_returncode()

    return [({"openkat/nmap-output"}, output.stdout.decode())]
