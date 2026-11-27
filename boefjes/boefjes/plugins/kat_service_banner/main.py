import socket
from os import getenv

READ_BYTES = 1024
REQUEST_TIMEOUT = 5


def get_sock(ip, port, timeout):
    """returns a socket to the ip/port with the given timeout set or returns None.

    Uses create_connection so both IPv4 and IPv6 targets work. The previous
    AF_INET socket silently failed for every IPv6 IPPort, since IPPort.address
    can be an IPAddressV6.

    Raises socket.timeout (a TimeoutError) when the connection attempt itself
    times out, so the caller can distinguish it from a refused connection.
    """
    return socket.create_connection((ip, port), timeout=timeout)


def get_banner(sock, bytescount):
    """Tries to get the banner using the supplied socket,
    reading as many bytes as requested.

    A read timeout is NOT a task timeout: many services (HTTP, TLS, and
    others) accept the connection and wait for the client to speak first,
    so a server that sends no banner is normal. Like on base, it is
    reported as error/boefje; only the connect phase (see run) reports
    error/timeout. Any other read error is error/boefje too. The socket
    is always closed, so the caller never has to clean it up.
    """
    try:
        banner = sock.recv(bytescount)
    except TimeoutError:
        return [({"error/boefje"}, "Unable to get banner. The service sent no banner")]
    except Exception as e:
        return [({"error/boefje"}, f"Unable to get banner. {str(e)}")]
    finally:
        sock.close()
    try:
        banner = banner.decode().strip()
    except UnicodeDecodeError:
        banner = banner.decode("latin1").strip()
    return [({"openkat/service-banner"}, banner)]


def run(boefje_meta: dict) -> list[tuple[set, str | bytes]]:
    """returns the service banner if available as a raw file
    takes an IPPort object as input"""
    input_ = boefje_meta["arguments"]["input"]  # input is IPPort
    port = input_["port"]
    ip = input_["address"]["address"]

    timeout = int(getenv("REQUEST_TIMEOUT", str(REQUEST_TIMEOUT)))
    try:
        sock = get_sock(ip, port, timeout)
    except TimeoutError:
        return [({"error/timeout"}, f"Connecting to {ip}:{port} timed out after {timeout} seconds")]
    except OSError:
        return [({"error/boefje"}, "Unable to connect to the service")]

    try:
        return get_banner(sock, int(getenv("READ_BYTES", str(READ_BYTES))))
    except TimeoutError:  # pragma: no cover - get_banner handles its own read timeout
        return [({"error/boefje"}, "Unable to get banner. The service sent no banner")]
