import json
import logging
from ipaddress import ip_address
from os import getenv

import requests
import shodan

from boefjes.plugins.helpers import _is_wrapped_timeout, session_timeout_adapters, set_session_timeout

DEFAULT_TIMEOUT = 30


def _client_session(api) -> requests.Session | None:
    """The requests session the shodan client uses. This is a private attribute
    (``api._session``), so tolerate a client upgrade that removes or renames
    it: the timeout injection and adapter-flag fallback degrade gracefully to
    the exception-chain classification, which needs no session."""
    return getattr(api, "_session", None)


def _request_timed_out(exc: Exception, session) -> bool:
    """Classify a shodan client failure as a genuine timeout.

    The client wraps every request-phase exception in
    APIError("Unable to connect to Shodan"), erasing the type — but the
    original exception survives in __context__ (implicit exception chaining),
    where a urllib3/socket timeout can be recognized. A read timeout while
    consuming the response body happens after HTTPAdapter.send() returned, so
    it neither sets the adapter flag nor (for body reads) reaches the client's
    wrapper: it surfaces from api.host() as a plain requests exception, which
    is why the session's adapters are consulted as a fallback.
    """
    if isinstance(exc, requests.exceptions.Timeout) or _is_wrapped_timeout(exc):
        return True
    return any(adapter.timed_out for adapter in session_timeout_adapters(session))


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    api = shodan.Shodan(getenv("SHODAN_API"))
    input_ = boefje_meta["arguments"]["input"]
    ip = input_["address"]
    results = {}
    session = _client_session(api)

    # The shodan client does not expose a request timeout; inject one into the
    # session the client uses via a TimeoutAdapter. Can be overridden through
    # the plugin settings, see schema.json.
    if session is not None:
        set_session_timeout(session, int(getenv("TIMEOUT", str(DEFAULT_TIMEOUT))))

    if ip_address(ip).is_private:
        return [({"openkat/deschedule"}, "Private IP requested, I will not forward this to Shodan.")]
    try:
        results = api.host(ip)
    except shodan.APIError as e:
        if e.args[0] == "No information available for that IP.":
            logging.info(e)
        elif e.args[0] == "Unable to connect to Shodan":
            # The client's blanket wrapper: classify via the preserved
            # exception chain, falling back to the adapter's timeout flag.
            if _request_timed_out(e, session):
                return [({"error/timeout"}, f"Request to Shodan timed out for {ip}")]
            raise
        else:
            raise
    except requests.exceptions.RequestException as exc:
        # A timeout while reading the response body escapes the client's
        # wrapper entirely (body consumption happens outside its try block).
        if _request_timed_out(exc, session):
            return [({"error/timeout"}, f"Request to Shodan timed out for {ip}")]
        raise

    return [(set(), json.dumps(results))]
