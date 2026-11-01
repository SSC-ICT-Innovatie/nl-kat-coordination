import socket
from os import getenv

READ_BYTES = 1024
REQUEST_TIMEOUT = 5


def get_sock(ip, port, timeout):
    """returns a socket to the ip/port with the given timeout set or returns None.

    Uses create_connection so both IPv4 and IPv6 targets work. The previous
    AF_INET socket silently failed for every IPv6 IPPort, since IPPort.address
    can be an IPAddressV6.
    """
    try:
        return socket.create_connection((ip, port), timeout=timeout)
    except OSError:
        return None


def get_banner(sock, bytescount):
    """Tries to get the banner using the supplied socket,
    reading as many bytes as requested"""
    try:
        banner = sock.recv(bytescount)
        try:
            banner = banner.decode().strip()
        except UnicodeDecodeError:
            banner = banner.decode("latin1").strip()
        sock.close()
        return [({"openkat/service-banner"}, banner)]
    except Exception as e:
        return [({"error/boefje"}, f"Unable to get banner. {str(e)}")]


def run(boefje_meta: dict) -> list[tuple[set, str | bytes]]:
    """returns the service banner if available as a raw file
    takes an IPPort object as input"""
    input_ = boefje_meta["arguments"]["input"]  # input is IPPort
    port = input_["port"]
    ip = input_["address"]["address"]

    sock = get_sock(ip, port, int(getenv("REQUEST_TIMEOUT", str(REQUEST_TIMEOUT))))
    if not sock:
        return [({"error/boefje"}, "Unable to connect to the service")]

    return get_banner(sock, int(getenv("READ_BYTES", str(READ_BYTES))))
