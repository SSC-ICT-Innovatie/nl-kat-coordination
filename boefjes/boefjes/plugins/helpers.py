import socket
from os import getenv

import requests


def cpe_to_name_version(cpe: str) -> tuple[str | None, str | None]:
    """Fetch the software name and version from a CPE string."""
    cpe_split = cpe.split(":")
    cpe_split_len = len(cpe_split)
    name = None if cpe_split_len < 4 else cpe_split[3]
    version = None if cpe_split_len < 5 else cpe_split[4]
    return name, version


# Default network timeouts in seconds: how long to wait to establish a connection, and
# how long to wait for data once connected. Both are overridable per boefje through the
# CONNECT_TIMEOUT and READ_TIMEOUT settings, see each boefje's schema.json.
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 30


def get_connect_and_read_timeout() -> tuple[int, int]:
    """Resolve the CONNECT_TIMEOUT and READ_TIMEOUT boefje settings to a requests timeout tuple.

    Boefje settings configured through the UI (schema.json) arrive as environment variables.
    Resolved at call time, so a running worker picks up changed settings without a restart.
    """
    connect_timeout = int(getenv("CONNECT_TIMEOUT", str(DEFAULT_CONNECT_TIMEOUT)))
    read_timeout = int(getenv("READ_TIMEOUT", str(DEFAULT_READ_TIMEOUT)))
    return connect_timeout, read_timeout


class TimeoutAdapter(requests.adapters.HTTPAdapter):
    """HTTPAdapter that applies a default timeout to every request it sends.

    requests only honors a timeout passed per request, and Session.request()
    always passes timeout explicitly (None by default). So a missing timeout
    arrives here as the key being present with the value None, not as an absent
    key: setdefault would keep None and the timeout would never apply.

    When a request through this adapter fails with a timeout, the ``timed_out``
    flag is set — and stays set until ``reset()`` is called. It answers "has a
    request through this adapter timed out since the last reset?", which lets
    clients like shodan classify their generic wrapped errors even when the
    underlying exception type is lost.
    """

    def __init__(self, timeout: float, **kwargs):
        self._timeout = timeout
        self.timed_out = False
        super().__init__(**kwargs)

    def send(self, *args, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        try:
            return super().send(*args, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            # requests wraps a streamed/read timeout in a plain ConnectionError
            # (see urllib3 ReadTimeoutError), so both count if the cause is
            # actually a timeout.
            if isinstance(exc, requests.exceptions.Timeout) or _is_wrapped_timeout(exc):
                self.timed_out = True
            raise

    def reset(self) -> None:
        self.timed_out = False


def _is_wrapped_timeout(exc: Exception) -> bool:
    """True if the exception chain bottoms out in a timeout (urllib3 or socket).

    Only the explicit urllib3/socket timeout classes are recognized (not a
    name-substring heuristic), and an exception raised with ``raise ... from
    None`` ends the walk: __suppress_context__ means the author declared the
    context irrelevant.
    """
    seen = set()
    current = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
    while current is not None and id(current) not in seen:
        if isinstance(current, TimeoutError | socket.timeout):
            return True
        if type(current).__name__ in ("ReadTimeoutError", "ConnectTimeoutError"):
            return True
        seen.add(id(current))
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    return False


def is_request_timeout(exc: Exception) -> bool:
    """True for a genuine requests timeout, including the wrapped case: requests
    raises a plain ConnectionError (chaining urllib3's ReadTimeoutError) when a
    read times out while consuming a response body, because that happens after
    HTTPAdapter.send() has returned. A refused connection or DNS failure is NOT
    a timeout.
    """
    return isinstance(exc, requests.exceptions.Timeout) or _is_wrapped_timeout(exc)


def session_timeout_adapters(session: requests.Session | None) -> list[TimeoutAdapter]:
    """The TimeoutAdapters mounted on this session, if any. Accepts None so
    clients with an optional/absent session (see kat_shodan) degrade to the
    exception-chain classification instead of raising."""
    if session is None:
        return []
    return [a for a in session.adapters.values() if isinstance(a, TimeoutAdapter)]


def set_session_timeout(session: requests.Session, timeout: float) -> None:
    """Bound every request of this session with the given timeout."""
    for prefix in ("http://", "https://"):
        session.mount(prefix, TimeoutAdapter(timeout))
