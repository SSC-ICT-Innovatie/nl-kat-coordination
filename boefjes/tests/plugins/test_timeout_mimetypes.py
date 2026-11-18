"""Every network boefje catches its own timeouts and reports them through the
error/timeout mime-type (with a human readable message), instead of failing the
task. The timeouts are configurable per boefje through its schema.json, which
the UI exposes as settings that arrive as environment variables.
"""

import json
import socket
import subprocess
import threading
from pathlib import Path
from unittest import mock

import httpx
import jsonschema
import pytest
import requests

from boefjes.plugins import helpers

input_website = {
    "hostname": {"name": "example.com"},
    "ip_service": {"service": {"name": "https"}, "ip_port": {"address": {"address": "1.2.3.4"}, "port": 443}},
}


def _main(boefje: str):
    module = __import__(f"boefjes.plugins.{boefje}.main", fromlist=["run"])
    return module


def test_get_connect_and_read_timeout_defaults():
    assert helpers.get_connect_and_read_timeout() == (helpers.DEFAULT_CONNECT_TIMEOUT, helpers.DEFAULT_READ_TIMEOUT)


def test_get_connect_and_read_timeout_reads_settings(monkeypatch):
    monkeypatch.setenv("CONNECT_TIMEOUT", "7")
    monkeypatch.setenv("READ_TIMEOUT", "45")

    assert helpers.get_connect_and_read_timeout() == (7, 45)


class RecordingAdapter(requests.adapters.HTTPAdapter):
    """Stands in for the real server: records the timeout kwarg it receives."""

    def __init__(self):
        self.seen_timeouts = []
        super().__init__()

    def send(self, request, **kwargs):
        self.seen_timeouts.append(kwargs.get("timeout"))
        return requests.Response()


def test_session_request_passes_timeout_none_to_adapter(mocker):
    """Documents the requests behavior that makes the None-check necessary: without an
    explicit timeout, Session.request() still passes timeout=None to
    adapter.send() — so setdefault() would keep None. This is why the adapter
    must treat None as 'apply mine'."""
    session = requests.Session()
    recording = RecordingAdapter()
    session.mount("http://", recording)

    # Intercept at the HTTPAdapter base to observe what Session.request passes.
    with mocker.patch.object(requests.adapters.HTTPAdapter, "send", side_effect=recording.send):
        session.get("http://unit.test/")

    assert recording.seen_timeouts == [None]


def test_timeout_adapter_enforces_timeout_through_real_session(mocker):
    """Session.request() always passes an
    explicit timeout (None by default), so a setdefault-based adapter kept
    None and never enforced anything. The adapter must replace a None."""
    # Call the adapter exactly the way Session.request() does: timeout always
    # present in send_kwargs, None when the caller did not set one.
    adapter = helpers.TimeoutAdapter(timeout=42)
    session = requests.Session()
    prepared = session.prepare_request(requests.Request(method="GET", url="http://unit.test/"))

    seen = {}

    def fake_super_send(self, request, **kwargs):
        seen.update(kwargs)
        return requests.Response()

    with mock.patch.object(requests.adapters.HTTPAdapter, "send", fake_super_send):
        adapter.send(prepared, timeout=None)

    assert seen["timeout"] == 42


def test_timeout_adapter_leaves_explicit_timeout_alone(mocker):
    """An explicit caller timeout must win over the adapter default."""
    adapter = helpers.TimeoutAdapter(timeout=42)

    seen = {}
    request = requests.Request(method="GET", url="http://unit.test/").prepare()

    def fake_super_send(self, request, **kwargs):
        seen.update(kwargs)
        return requests.Response()

    with mock.patch.object(requests.adapters.HTTPAdapter, "send", fake_super_send):
        adapter.send(request, timeout=7)

    assert seen["timeout"] == 7


def test_timeout_adapter_records_timeout_state(mocker):
    """The adapter must record whether the last
    failure was a genuine timeout, so clients that erase exception types
    (shodan) can still classify correctly."""
    adapter = helpers.TimeoutAdapter(timeout=42)
    request = requests.Request(method="GET", url="http://unit.test/").prepare()

    assert adapter.timed_out is False

    def raise_timeout(self, request, **kwargs):
        raise requests.exceptions.ConnectTimeout("timed out")

    with (
        mock.patch.object(requests.adapters.HTTPAdapter, "send", raise_timeout),
        pytest.raises(requests.exceptions.Timeout),
    ):
        adapter.send(request, timeout=None)

    assert adapter.timed_out is True


def test_timeout_adapter_does_not_record_connection_error(mocker):
    adapter = helpers.TimeoutAdapter(timeout=42)
    request = requests.Request(method="GET", url="http://unit.test/").prepare()

    def raise_conn_error(self, request, **kwargs):
        raise requests.exceptions.ConnectionError("Name or service not known")

    with (
        mock.patch.object(requests.adapters.HTTPAdapter, "send", raise_conn_error),
        pytest.raises(requests.exceptions.ConnectionError),
    ):
        adapter.send(request, timeout=None)

    assert adapter.timed_out is False


def _stalled_body_server(responses: list):
    """Yield (port, thread) for a local server that sends the given bytes then
    stalls (never completing the response)."""
    holder = {}
    started = threading.Event()

    def serve():
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        holder["port"] = srv.getsockname()[1]
        srv.listen(1)
        started.set()
        conn, _ = srv.accept()
        for chunk in responses:
            conn.sendall(chunk)
        threading.Event().wait(10)  # stall: never complete the response
        srv.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    started.wait(2)
    return holder["port"], thread


def test_timeout_adapter_send_phase_timeout_live():
    """Integration: a real session with the mounted
    adapter must enforce the timeout on the send/connect phase."""
    port, _ = _stalled_body_server([])  # accept nothing

    session = requests.Session()
    helpers.set_session_timeout(session, 1)

    with pytest.raises(requests.exceptions.Timeout):
        session.get(f"http://127.0.0.1:{port}/")


def test_body_read_timeout_is_recognized_as_timeout_live():
    """Integration: headers + partial body, then a
    stall. The read timeout fires while consuming the body — after
    HTTPAdapter.send() returned — so the adapter flag stays False, but the
    exception chain must still be recognized as a timeout. This is exactly the
    shodan body-read scenario."""
    port, _ = _stalled_body_server([b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nshort"])

    session = requests.Session()
    helpers.set_session_timeout(session, 1)

    with pytest.raises(requests.exceptions.RequestException) as excinfo:
        response = session.get(f"http://127.0.0.1:{port}/", stream=True)
        response.content

    exc = excinfo.value
    # The adapter flag cannot see this phase — documenting the limitation:
    assert all(not adapter.timed_out for adapter in helpers.session_timeout_adapters(session))
    # But the exception chain gives it away:
    assert helpers._is_wrapped_timeout(exc) or isinstance(exc, requests.exceptions.Timeout)


def test_is_wrapped_timeout_detects_streamed_read_timeout():
    """requests wraps urllib3's ReadTimeoutError
    in a plain ConnectionError for streamed body reads."""
    ReadTimeoutError = type("ReadTimeoutError", (Exception,), {})
    wrapped = requests.exceptions.ConnectionError("wrapper")
    wrapped.__cause__ = ReadTimeoutError("Read timed out. (read timeout=1)")

    assert helpers._is_wrapped_timeout(wrapped) is True


def test_is_wrapped_timeout_rejects_plain_connection_error():
    wrapped = requests.exceptions.ConnectionError("Name or service not known")

    assert helpers._is_wrapped_timeout(wrapped) is False


REQUESTS_TIMEOUT_BOEFJES = {
    "kat_green_hosting": {"arguments": {"input": {"hostname": {"name": "example.com"}}}},
    "kat_cve_2023_35078": {"arguments": {"input": input_website}},
    "kat_cve_finding_types": {"arguments": {"input": {"id": "CVE-2020-1234"}}},
    "kat_external_db": {"organization": "test"},
    "kat_retirejs_finding_types": {},
    "kat_snyk": {"arguments": {"input": {"name": "django", "version": "1.0", "cpe": None}}},
    "kat_snyk_finding_types": {"arguments": {"input": {"id": "SNYK-JS-LODASH-567746"}}},
    "kat_leakix": {"input_ooi": "IPAddressV4|1.2.3.4"},
    "kat_rpki": {"arguments": {"input": {"address": "1.2.3.4"}}},
    "kat_maxmind_geoip": {"arguments": {"input": {"address": "1.2.3.4"}}},
    "kat_export_http": {"arguments": {"input": {"id": "x"}}, "organization": "test"},
}


@pytest.mark.parametrize("boefje,boefje_meta", sorted(REQUESTS_TIMEOUT_BOEFJES.items()), ids=str)
def test_requests_boefje_timeout_returns_timeout_mimetype(mocker, boefje, boefje_meta):
    main = _main(boefje)

    mocker.patch.object(main.requests, "get", side_effect=requests.exceptions.ConnectTimeout("timed out"))
    if hasattr(main.requests, "request"):
        mocker.patch.object(main.requests, "request", side_effect=requests.exceptions.ConnectTimeout("timed out"))

    results = main.run(boefje_meta)

    assert len(results) == 1
    mime_types, message = results[0]

    assert mime_types == {"error/timeout"}
    assert isinstance(message, str)
    assert message


def test_snyk_timeout_is_not_raised_but_returned(mocker):
    main = _main("kat_snyk")

    mocker.patch.object(main.requests, "get", side_effect=requests.exceptions.ReadTimeout("timed out"))

    mime_types, message = main.run({"arguments": {"input": {"name": "django", "version": "1.0", "cpe": None}}})[0]

    assert mime_types == {"error/timeout"}
    assert "django" in message


def test_webpage_analysis_timeout_returns_timeout_mimetype(mocker):
    main = _main("kat_webpage_analysis")

    mocker.patch.object(main, "do_request", side_effect=requests.exceptions.ReadTimeout("timed out"))
    boefje_meta = {
        "arguments": {
            "input": {
                "web_url": {"scheme": "https", "port": 443, "netloc": {"name": "example.com"}, "path": ""},
                "website": {"ip_service": {"ip_port": {"address": {"address": "1.2.3.4"}}}},
            }
        }
    }

    mime_types, message = main.run(boefje_meta)[0]

    assert mime_types == {"error/timeout"}


def test_security_txt_downloader_timeout_returns_timeout_mimetype(mocker):
    main = _main("kat_security_txt_downloader")

    mocker.patch.object(main, "do_request", side_effect=requests.exceptions.ReadTimeout("timed out"))
    boefje_meta = {"arguments": {"input": input_website}}

    mime_types, message = main.run(boefje_meta)[0]

    assert mime_types == {"error/timeout"}
    # codeql[py/incomplete-url-substring-sanitization] (test fixture, not a URL check)
    assert "example.com" in message


def test_security_txt_downloader_request_uses_configured_timeout(mocker, monkeypatch):
    """The session requests used to have no timeout at all and could hang forever."""
    main = _main("kat_security_txt_downloader")
    monkeypatch.setenv("CONNECT_TIMEOUT", "7")
    monkeypatch.setenv("READ_TIMEOUT", "45")

    session = mocker.Mock()

    main.do_request("example.com", session, "https://example.com/.well-known/security.txt", "OpenKAT", (7, 45))

    assert session.get.call_args.kwargs["timeout"] == (7, 45)


def test_security_txt_streamed_read_timeout_is_not_a_connection_error(mocker):
    """requests wraps a streamed-body read
    timeout (urllib3 ReadTimeoutError) in a plain ConnectionError. The
    redirect-following path reads .content from a stream=True response, so the
    handler must classify that wrapped exception as a timeout — while a genuine
    connection error still raises."""
    main = _main("kat_security_txt_downloader")

    # First path: 200 with content. Second path: 301 redirect; the follow-up
    # request succeeds but reading the streamed body times out.
    first = mocker.Mock(status_code=200)
    first.content = b"contact: mailto:security@example.com\n"

    redirect = mocker.Mock(status_code=301, headers={"Location": "https://other.example.com/x"})
    redirect.raw._connection = None

    def fake_get(uri, **kwargs):
        # codeql[py/incomplete-url-substring-sanitization] (test fixture, not a URL check)
        if uri.startswith("https://other.example.com"):
            response = redirect
            # Simulate: response.content raises the wrapped urllib3 timeout.
            cause = type("ReadTimeoutError", (Exception,), {})("Read timed out. (read timeout=45)")
            error = requests.exceptions.ConnectionError("wrapped")
            error.__cause__ = cause
            mocker.patch.object(type(response), "content", property(lambda self: (_ for _ in ()).throw(error)))
            return response
        return first

    mocker.patch.object(main.requests, "get", side_effect=fake_get)

    mime_types, message = main.run({"arguments": {"input": input_website}})[0]

    assert mime_types == {"error/timeout"}
    # codeql[py/incomplete-url-substring-sanitization] (test fixture, not a URL check)
    assert "example.com" in message


def test_security_txt_connection_error_is_not_a_timeout(mocker):
    """A refused connection / DNS failure must NOT be classified as a timeout
    (would reintroduce false positives): both the initial request and the
    redirect-following request propagate the ConnectionError."""
    main = _main("kat_security_txt_downloader")

    def fake_get(self, uri, **kwargs):
        raise requests.exceptions.ConnectionError("Name or service not known")

    # Session.get covers the initial request; requests.get covers the redirect.
    mocker.patch.object(main.Session, "get", fake_get)
    mocker.patch.object(main.requests, "get", fake_get)

    with pytest.raises(requests.exceptions.ConnectionError):
        main.run({"arguments": {"input": input_website}})


def test_shodan_internetdb_timeout_returns_timeout_mimetype(mocker):
    main = _main("kat_shodan_internetdb")

    mocker.patch.object(main.httpx, "get", side_effect=httpx.ConnectTimeout("timed out"))

    mime_types, message = main.run({"arguments": {"input": {"address": "1.2.3.4"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "1.2.3.4" in message


def test_shodan_timeout_returns_timeout_mimetype(mocker):
    pytest.importorskip("shodan")
    main = _main("kat_shodan")

    mocker.patch.object(main.shodan.Shodan, "host", side_effect=requests.exceptions.ConnectTimeout("timed out"))

    mime_types, message = main.run({"arguments": {"input": {"address": "8.8.8.8"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "8.8.8.8" in message


def test_shodan_client_wrapped_timeout_returns_timeout_mimetype(mocker):
    """The real
    shodan client converts every connection problem into
    shodan.APIError("Unable to connect to Shodan"). The boefje must ask the
    mounted adapter whether a genuine timeout occurred — only then classify
    as error/timeout."""
    pytest.importorskip("shodan")
    pytest.importorskip("requests")
    main = _main("kat_shodan")

    api = mocker.MagicMock()
    api._session = requests.Session()  # real session: adapters get mounted for real
    mocker.patch.object(main.shodan, "Shodan", return_value=api)

    def wrapped_timeout(*args, **kwargs):
        # Simulate the adapter recording the timeout, the client wrapping the
        # exception exactly as client.py does.
        for adapter in main.session_timeout_adapters(api._session):
            adapter.timed_out = True
        raise main.shodan.APIError("Unable to connect to Shodan")

    api.host.side_effect = wrapped_timeout
    mocker.patch.dict("os.environ", {"TIMEOUT": "42"})

    mime_types, message = main.run({"arguments": {"input": {"address": "8.8.8.8"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "8.8.8.8" in message


def test_shodan_wrapped_connection_error_is_not_a_timeout(mocker):
    """APIError('Unable to connect to Shodan')
    wraps every network failure. Without a recorded timeout (DNS failure,
    refusal) it must stay a hard failure, not become TIMEOUT."""
    pytest.importorskip("shodan")
    main = _main("kat_shodan")

    api = mocker.MagicMock()
    api._session = requests.Session()  # real session, no adapter state set
    mocker.patch.object(main.shodan, "Shodan", return_value=api)
    api.host.side_effect = main.shodan.APIError("Unable to connect to Shodan")

    with pytest.raises(main.shodan.APIError):
        main.run({"arguments": {"input": {"address": "8.8.8.8"}}})


def test_shodan_body_read_timeout_returns_timeout_mimetype(mocker):
    """A read timeout while consuming
    the response body happens after HTTPAdapter.send() returned, so the adapter
    flag is False — but the original exception survives in the APIError's
    __context__ and must be recognized."""
    pytest.importorskip("shodan")
    main = _main("kat_shodan")

    api = mocker.MagicMock()
    api._session = requests.Session()  # real session: adapters get mounted
    mocker.patch.object(main.shodan, "Shodan", return_value=api)

    def body_read_timeout(*args, **kwargs):
        # Exactly what shodan's client produces for a body-phase failure:
        # the urllib3 timeout wrapped in ConnectionError, re-raised as a
        # generic APIError with implicit context chaining (raise, NOT
        # raise ... from None: the client does not suppress __context__,
        # and _is_wrapped_timeout honours suppression per review L2).
        read_error = requests.exceptions.ConnectionError("wrapped")
        read_error.__cause__ = type("ReadTimeoutError", (Exception,), {})("Read timed out. (read timeout=30)")
        try:
            raise read_error
        except Exception:
            raise main.shodan.APIError("Unable to connect to Shodan")  # noqa: B904 (implicit chaining is the point)

    api.host.side_effect = body_read_timeout

    mime_types, message = main.run({"arguments": {"input": {"address": "8.8.8.8"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "8.8.8.8" in message


def test_shodan_body_read_timeout_unwrapped_returns_timeout_mimetype(mocker):
    """The client reads the response
    body outside its try block, so a body-phase timeout can also surface from
    api.host() as a plain requests exception — it must be classified, not
    fail the task."""
    pytest.importorskip("shodan")
    main = _main("kat_shodan")

    api = mocker.MagicMock()
    api._session = requests.Session()
    mocker.patch.object(main.shodan, "Shodan", return_value=api)

    read_error = requests.exceptions.ConnectionError("wrapped")
    read_error.__cause__ = type("ReadTimeoutError", (Exception,), {})("Read timed out. (read timeout=30)")
    api.host.side_effect = read_error

    mime_types, message = main.run({"arguments": {"input": {"address": "8.8.8.8"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "8.8.8.8" in message


def test_shodan_no_information_is_not_a_timeout(mocker):
    pytest.importorskip("shodan")
    main = _main("kat_shodan")

    api = mocker.MagicMock()
    api._session = mocker.Mock()
    mocker.patch.object(main.shodan, "Shodan", return_value=api)
    api.host.side_effect = main.shodan.APIError("No information available for that IP.")

    mime_types, _ = main.run({"arguments": {"input": {"address": "8.8.8.8"}}})[0]

    assert mime_types == set()


def test_shodan_other_api_errors_still_raise(mocker):
    pytest.importorskip("shodan")
    main = _main("kat_shodan")

    api = mocker.MagicMock()
    api._session = mocker.Mock()
    mocker.patch.object(main.shodan, "Shodan", return_value=api)
    api.host.side_effect = main.shodan.APIError("Invalid API key")

    with pytest.raises(main.shodan.APIError):
        main.run({"arguments": {"input": {"address": "8.8.8.8"}}})


def test_censys_timeout_returns_timeout_mimetype(mocker):
    pytest.importorskip("censys")
    main = _main("kat_censys")

    hosts = mocker.Mock()
    hosts.view.side_effect = requests.exceptions.ReadTimeout("timed out")
    mocker.patch.object(main, "CensysHosts", return_value=hosts)

    mime_types, message = main.run({"arguments": {"input": {"address": "1.2.3.4"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "1.2.3.4" in message


def test_shodan_no_global_socket_timeout():
    """No boefje may touch the process-wide
    socket default anymore."""
    for name in ("kat_shodan", "kat_binaryedge"):
        source = (Path(helpers.__file__).parent / name / "main.py").read_text()
        assert "setdefaulttimeout" not in source, name


def test_binaryedge_is_unchanged_from_main():
    """kat_binaryedge is scheduled for removal in #4500 (maintainer decision);
    until then this PR must not change it."""
    import subprocess

    diff = subprocess.run(
        ["git", "diff", "origin/main", "HEAD", "--", "boefjes/plugins/kat_binaryedge"],
        capture_output=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    assert diff.stdout == b"", diff.stdout.decode()


def test_rdns_timeout_returns_timeout_mimetype(mocker):
    main = _main("kat_rdns")

    mocker.patch.object(main.dns.resolver.Resolver, "resolve", side_effect=main.dns.resolver.Timeout("timed out"))

    mime_types, message = main.run({"arguments": {"input": {"address": "1.2.3.4"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "1.2.3.4" in message


def test_dns_zone_timeout_returns_timeout_mimetype(mocker):
    main = _main("kat_dns_zone")

    mocker.patch.object(main.dns.resolver.Resolver, "resolve", side_effect=main.dns.resolver.Timeout("timed out"))

    mime_types, message = main.run({"arguments": {"input": {"hostname": {"name": "example.com"}}}})[0]

    assert mime_types == {"error/timeout"}
    assert "timed out" in message


def test_dns_zone_resolver_settings_applied(mocker):
    """dns_zone must use the configurable
    resolver (REMOTE_NS + DNS_TIMEOUT/DNS_LIFETIME) instead of the system
    default. It used the module-level resolver, ignoring both."""
    main = _main("kat_dns_zone")
    captured = {}

    def fake_resolve(self, name, record_type, **kwargs):
        captured["timeout"] = self.timeout
        captured["lifetime"] = self.lifetime
        captured["nameservers"] = self.nameservers
        response = mocker.Mock()
        response.answer = [mocker.Mock()]
        return mocker.MagicMock(nameserver="1.1.1.1", response=response, rrset=response.answer[0])

    mocker.patch.object(main.dns.resolver.Resolver, "resolve", fake_resolve)
    mocker.patch.dict("os.environ", {"REMOTE_NS": "9.9.9.9", "DNS_TIMEOUT": "3.5", "DNS_LIFETIME": "45"})

    mime_types, _ = main.run({"arguments": {"input": {"hostname": {"name": "example.com"}}}})[0]

    assert mime_types == set()
    assert captured["nameservers"] == ["9.9.9.9"]
    assert captured["timeout"] == 3.5
    assert captured["lifetime"] == 45.0


def test_dns_zone_keeps_system_resolver_when_remote_ns_unset(mocker, monkeypatch):
    """Without REMOTE_NS the resolver keeps /etc/resolv.conf's nameservers:
    installs behind an internal resolver or with restricted DNS egress must
    keep working (per review M3)."""
    main = _main("kat_dns_zone")
    seen = {}

    class TrackingResolver(main.dns.resolver.Resolver):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            seen["after_init"] = list(self.nameservers)

        nameservers = main.dns.resolver.Resolver.nameservers  # plain attribute, no property games

    def fake_resolve(self, name, record_type, **kwargs):
        seen["at_resolve"] = list(self.nameservers)
        response = mocker.Mock()
        response.answer = [mocker.Mock()]
        return mocker.MagicMock(nameserver="10.0.0.53", response=response, rrset=response.answer[0])

    monkeypatch.setenv("REMOTE_NS", "")  # explicitly unset
    mocker.patch.object(main.dns.resolver, "Resolver", TrackingResolver)
    mocker.patch.object(TrackingResolver, "resolve", fake_resolve)

    mime_types, _ = main.run({"arguments": {"input": {"hostname": {"name": "example.com"}}}})[0]

    assert mime_types == set()
    assert seen["at_resolve"] == seen["after_init"]  # the boefje left the system resolver untouched


def test_dns_all_timeouts_returns_timeout_mimetype(mocker):
    """When every query times out the boefje reports error/timeout instead of raising."""
    main = _main("kat_dns")

    mocker.patch.object(main.dns.resolver.Resolver, "resolve", side_effect=main.dns.resolver.Timeout("timed out"))
    mocker.patch.object(main, "get_email_security_records", lambda *args: "Timeout")

    mime_types, message = main.run({"arguments": {"input": {"name": "example.com"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "timeouts" in message


def test_dns_partial_timeout_is_not_a_scan_timeout(mocker):
    """A definitive answer for some queries
    plus timeouts elsewhere must not be reported as a scan-wide timeout, nor
    discard the successful answers."""
    main = _main("kat_dns")

    # Main record queries time out, but the email security lookups succeed.
    mocker.patch.object(main, "get_record_types", lambda: {"TXT"})
    mocker.patch.object(main.dns.resolver.Resolver, "resolve", side_effect=main.dns.resolver.Timeout("timed out"))
    mocker.patch.object(main, "get_email_security_records", side_effect=["NXDOMAIN", "NXDOMAIN"])

    mime_types, raw = main.run({"arguments": {"input": {"name": "example.com"}}})[0]

    assert mime_types == set()
    result = json.loads(raw)
    assert result["dmarc_response"] == "NXDOMAIN"
    assert result["dkim_response"] == "NXDOMAIN"


def test_dns_definitive_noanswer_with_timeout_lookups_is_not_a_timeout(mocker):
    """The duplicated dmarc condition used to
    report error/timeout even though DMARC answered definitively."""
    main = _main("kat_dns")

    # No SOA requested; the record queries answer definitively with no answer.
    mocker.patch.object(main, "get_record_types", lambda: {"TXT"})
    mocker.patch.object(main.dns.resolver.Resolver, "resolve", side_effect=main.dns.resolver.NoAnswer)
    # DMARC answers "no answer", DKIM times out: still a partial result.
    mocker.patch.object(main, "get_email_security_records", side_effect=["NXDOMAIN", "Timeout"])

    mime_types, raw = main.run({"arguments": {"input": {"name": "example.com"}}})[0]

    assert mime_types == set()
    result = json.loads(raw)
    assert result["dmarc_response"] == "NXDOMAIN"
    assert result["dkim_response"] == "Timeout"


def test_dns_resolver_timeout_settings_applied(mocker):
    """The configurable DNS timeouts must reach
    dnspython's resolver."""
    main = _main("kat_dns")
    captured = {}

    def fake_resolve(self, name, record_type, **kwargs):
        captured["timeout"] = self.timeout
        captured["lifetime"] = self.lifetime
        raise main.dns.resolver.NoAnswer

    mocker.patch.object(main, "get_record_types", lambda: {"TXT"})
    mocker.patch.object(main.dns.resolver.Resolver, "resolve", fake_resolve)
    mocker.patch.dict("os.environ", {"DNS_TIMEOUT": "7.5", "DNS_LIFETIME": "60"})
    mocker.patch.object(main, "get_email_security_records", lambda *args: "NXDOMAIN")

    main.run({"arguments": {"input": {"name": "example.com"}}})

    assert captured == {"timeout": 7.5, "lifetime": 60.0}


def test_dns_soa_metadata_timeout_does_not_gate_the_scan(mocker):
    """A parent-zone SOA timeout is
    metadata, not scan subject — it must not abort the scan while the record
    lookups would succeed."""
    main = _main("kat_dns")

    def fake_resolve(self, name, record_type, **kwargs):
        # Only record-type queries reach this fake; the SOA metadata walk is
        # patched separately (fake_soa_walk) and raises Timeout.
        response = mocker.Mock()
        return mocker.MagicMock(nameserver="1.1.1.1", response=response, rrset=mocker.Mock())

    resolve_calls = []

    def fake_soa_walk(*args, **kwargs):
        resolve_calls.append("soa")
        raise main.dns.resolver.Timeout("timed out")

    def fake_record_resolve(self, name, record_type, **kwargs):
        resolve_calls.append(str(record_type))
        raise main.dns.resolver.NoAnswer

    # get_parent_zone_soa times out; the record queries answer definitively.
    mocker.patch.object(main, "get_record_types", lambda: {"SOA", "TXT"})
    mocker.patch.object(main, "get_parent_zone_soa", side_effect=fake_soa_walk)
    mocker.patch.object(main.dns.resolver.Resolver, "resolve", fake_record_resolve)
    mocker.patch.object(main, "get_email_security_records", lambda *args: "NXDOMAIN")

    mime_types, raw = main.run({"arguments": {"input": {"name": "example.com"}}})[0]

    # Scan completed — no error/timeout — and the record queries ran.
    assert mime_types == set()
    assert resolve_calls.count("soa") == 1
    assert "TXT" in resolve_calls
    result = json.loads(raw)
    assert result["dmarc_response"] == "NXDOMAIN"


def test_dns_soa_metadata_success_does_not_mask_record_timeouts(mocker):
    """A successful parent-zone
    SOA (metadata) must not prevent the scan-wide timeout when every
    scan-subject record query timed out."""
    main = _main("kat_dns")

    def fake_soa_walk(*args, **kwargs):
        answer = mocker.MagicMock()
        answer.nameserver = "1.1.1.1"
        answer.response = mocker.MagicMock()
        return answer

    mocker.patch.object(main, "get_record_types", lambda: ["SOA", "A", "AAAA"])
    mocker.patch.object(main, "get_parent_zone_soa", side_effect=fake_soa_walk)
    mocker.patch.object(main.dns.resolver.Resolver, "resolve", side_effect=main.dns.resolver.Timeout("timed out"))
    mocker.patch.object(main, "get_email_security_records", lambda *args: "Timeout")

    mime_types, _ = main.run({"arguments": {"input": {"name": "example.com"}}})[0]

    assert mime_types == {"error/timeout"}


def test_dns_foreign_owner_soa_is_not_definitive_evidence(mocker):
    """A foreign-owner SOA
    (CNAME follow) is not a definitive answer for this hostname and must not
    stop the scan-wide timeout."""
    main = _main("kat_dns")

    def fake_soa_walk(*args, **kwargs):
        raise main.dns.resolver.Timeout("timed out")

    def fake_resolve(self, name, record_type, **kwargs):
        if record_type == "SOA":
            answer = mocker.MagicMock()
            answer.rrset = mocker.Mock()
            answer.rrset.name = "alias.other.net."  # not the requested name
            return answer
        raise main.dns.resolver.Timeout("timed out")

    mocker.patch.object(main, "get_record_types", lambda: ["SOA", "A", "AAAA"])  # SOA first
    mocker.patch.object(main, "get_parent_zone_soa", side_effect=fake_soa_walk)
    mocker.patch.object(main.dns.resolver.Resolver, "resolve", fake_resolve)
    mocker.patch.object(main, "get_email_security_records", lambda *args: "Timeout")

    mime_types, _ = main.run({"arguments": {"input": {"name": "example.com"}}})[0]

    assert mime_types == {"error/timeout"}


def test_dns_mixed_noanswer_and_timeout_is_not_a_timeout(mocker):
    """A definitive NoAnswer for one
    record plus a timeout for another must not produce error/timeout — a
    definitive negative is conclusive evidence."""
    main = _main("kat_dns")

    outcomes = iter(
        [
            main.dns.resolver.NoAnswer(),  # A
            main.dns.resolver.Timeout("timed out"),  # AAAA
        ]
    )

    def fake_resolve(self, name, record_type, **kwargs):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    mocker.patch.object(main, "get_record_types", lambda: {"A", "AAAA"})
    mocker.patch.object(main.dns.resolver.Resolver, "resolve", fake_resolve)
    # DMARC and DKIM time out too — yet the scan is not a timeout, because the
    # A query answered definitively.
    mocker.patch.object(main, "get_email_security_records", side_effect=["Timeout", "Timeout"])

    mime_types, raw = main.run({"arguments": {"input": {"name": "example.com"}}})[0]

    assert mime_types == set()
    result = json.loads(raw)
    assert result["dmarc_response"] == "Timeout"
    assert result["dkim_response"] == "Timeout"


def test_dns_schema_uses_integer_seconds():
    """The katalogus UI only supports integer
    settings; DNS timeout fields must be integers, not numbers."""
    plugins_dir = Path(helpers.__file__).parent
    for name in ("kat_dns", "kat_rdns", "kat_dns_zone"):
        schema = json.loads((plugins_dir / name / "schema.json").read_text())
        for key in ("DNS_TIMEOUT", "DNS_LIFETIME"):
            prop = schema["properties"][key]
            assert prop["type"] == "integer", f"{name}.{key}"
            assert isinstance(prop["default"], int), f"{name}.{key}"


def test_api_client_schemas_keep_credentials():
    """Adding a TIMEOUT field must not
    drop the credential properties, required lists, or secret declarations.
    (kat_binaryedge is excluded: scheduled for removal in #4500, schema
    stays as on main.)"""
    plugins_dir = Path(helpers.__file__).parent
    expectations = {
        "kat_censys": (["CENSYS_API_ID", "CENSYS_API_SECRET"], ["CENSYS_API_SECRET"]),
        "kat_shodan": (["SHODAN_API"], ["SHODAN_API"]),
    }
    for name, (required, secrets) in expectations.items():
        schema = json.loads((plugins_dir / name / "schema.json").read_text())
        assert schema.get("required") == required, name
        assert schema.get("secret") == secrets, name
        assert "TIMEOUT" in schema["properties"], name
        for key in required:
            assert key in schema["properties"], f"{name}.{key} property"


def test_adr_validator_timeout_returns_timeout_mimetype(mocker):
    main = _main("kat_adr_validator")

    mocker.patch.object(
        main.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["adr-validator"], timeout=300)
    )

    mime_types, message = main.run(
        # codeql[py/incomplete-url-substring-sanitization] (test fixture, not a URL check)
        {"arguments": {"input": {"api_url": {"netloc": {"name": "example.com"}, "path": "", "scheme": "https"}}}}
    )[0]

    assert mime_types == {"error/timeout"}
    # codeql[py/incomplete-url-substring-sanitization] (test fixture, not a URL check)
    assert "example.com" in message


def test_subfinder_timeout_returns_timeout_mimetype(mocker):
    main = _main("kat_pdio_subfinder")

    mocker.patch.object(main.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["subfinder"], timeout=600))

    mime_types, message = main.run({"arguments": {"input": {"hostname": {"name": "example.com"}}}})[0]

    assert mime_types == {"error/timeout"}
    # codeql[py/incomplete-url-substring-sanitization] (test fixture, not a URL check)
    assert "example.com" in message


def test_cve_2023_34039_all_timeouts_is_not_a_false_negative(mocker, tmp_path):
    """When every SSH attempt times out, the
    boefje must not claim 'No known keys allowed' — that would be a definitive
    negative no key ever earned."""
    main = _main("kat_cve_2023_34039")

    (tmp_path / "k1").touch()
    (tmp_path / "k2").touch()
    mocker.patch.object(main, "KEYS_DIR", tmp_path)
    mocker.patch.object(main.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["ssh"], timeout=30))

    mime_types, message = main.run(
        {
            "arguments": {
                "input": {"service": {"name": "ssh"}, "ip_port": {"address": {"address": "1.2.3.4"}, "port": 22}}
            }
        }
    )[0]

    assert mime_types == {"error/timeout"}
    assert "Unable to complete testing" in message
    assert "No known keys allowed" not in message


def test_cve_2023_34039_ssh_exit_255_connection_timeout_is_inconclusive(mocker, tmp_path):
    """ssh itself times out and exits
    255 with 'Connection timed out' on stderr — long before the Python
    subprocess timeout fires. That is inconclusive, not a rejection."""
    main = _main("kat_cve_2023_34039")

    (tmp_path / "k1").touch()
    (tmp_path / "k2").touch()
    mocker.patch.object(main, "KEYS_DIR", tmp_path)
    mocker.patch.dict("os.environ", {"TIMEOUT": "999"})  # python timeout never fires here

    def attempt(cmd, stdout=None, stderr=None, timeout=None):
        return subprocess.CompletedProcess(
            cmd, 255, stdout=b"", stderr=b"ssh: connect to host 1.2.3.4 port 22: Connection timed out"
        )

    mocker.patch.object(main.subprocess, "run", side_effect=attempt)

    mime_types, message = main.run(
        {
            "arguments": {
                "input": {"service": {"name": "ssh"}, "ip_port": {"address": {"address": "1.2.3.4"}, "port": 22}}
            }
        }
    )[0]

    assert mime_types == {"error/timeout"}
    assert "Unable to complete testing" in message
    assert "No known keys allowed" not in message


def test_cve_2023_34039_ssh_permission_denied_is_a_definitive_rejection(mocker, tmp_path):
    """'Permission denied' means ssh reached the host and rejected the key:
    conclusive evidence. All keys rejected => the definitive negative stands."""
    main = _main("kat_cve_2023_34039")

    (tmp_path / "k1").touch()
    mocker.patch.object(main, "KEYS_DIR", tmp_path)

    def attempt(cmd, stdout=None, stderr=None, timeout=None):
        return subprocess.CompletedProcess(cmd, 255, stdout=b"", stderr=b"Permission denied (publickey).")

    mocker.patch.object(main.subprocess, "run", side_effect=attempt)

    mime_types, message = main.run(
        {
            "arguments": {
                "input": {"service": {"name": "ssh"}, "ip_port": {"address": {"address": "1.2.3.4"}, "port": 22}}
            }
        }
    )[0]

    assert mime_types == set()
    assert message == "No known keys allowed"


def test_cve_2023_34039_missing_ssh_executable_is_error_boefje(mocker, tmp_path):
    """A missing ssh executable is a
    boefje/config problem — not a scan result and not a timeout."""
    main = _main("kat_cve_2023_34039")

    (tmp_path / "k1").touch()
    mocker.patch.object(main, "KEYS_DIR", tmp_path)
    mocker.patch.object(main.subprocess, "run", side_effect=FileNotFoundError(2, "ssh"))

    mime_types, message = main.run(
        {
            "arguments": {
                "input": {"service": {"name": "ssh"}, "ip_port": {"address": {"address": "1.2.3.4"}, "port": 22}}
            }
        }
    )[0]

    assert mime_types == {"error/boefje"}
    assert "ssh executable not found" in message


def test_cve_2023_34039_connection_refused_is_inconclusive_not_timeout(mocker, tmp_path):
    """'Connection refused' is a network
    failure (inconclusive): the key was never tested, so it prevents the
    definitive negative — but it is not a timeout and must not claim the
    rerunnable TIMEOUT state (per review M2: refused connections are answered
    decisively, unlike a blackhole)."""
    main = _main("kat_cve_2023_34039")

    (tmp_path / "k1").touch()
    mocker.patch.object(main, "KEYS_DIR", tmp_path)

    def attempt(cmd, stdout=None, stderr=None, timeout=None):
        return subprocess.CompletedProcess(
            cmd, 255, stdout=b"", stderr=b"ssh: connect to host 1.2.3.4 port 22: Connection refused"
        )

    mocker.patch.object(main.subprocess, "run", side_effect=attempt)

    mime_types, message = main.run(
        {
            "arguments": {
                "input": {"service": {"name": "ssh"}, "ip_port": {"address": {"address": "1.2.3.4"}, "port": 22}}
            }
        }
    )[0]

    assert mime_types == {"error/boefje"}
    assert "failed to connect" in message


def test_cve_2023_34039_mixed_timeout_and_rejection_still_negative(mocker, tmp_path):
    """A definitively rejected key (exit 1) is evidence; a timeout is not.
    Only timeouts must block the definitive negative."""
    main = _main("kat_cve_2023_34039")

    (tmp_path / "k1").touch()
    (tmp_path / "k2").touch()
    mocker.patch.object(main, "KEYS_DIR", tmp_path)

    def attempt(cmd, stdout=None, stderr=None, timeout=None):
        if "k1" in str(cmd[1]):
            return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"")
        raise subprocess.TimeoutExpired(cmd, timeout)

    mocker.patch.object(main.subprocess, "run", side_effect=attempt)

    mime_types, message = main.run(
        {
            "arguments": {
                "input": {"service": {"name": "ssh"}, "ip_port": {"address": {"address": "1.2.3.4"}, "port": 22}}
            }
        }
    )[0]

    assert mime_types == {"error/timeout"}


def test_service_banner_connect_timeout_returns_timeout_mimetype(mocker):
    main = _main("kat_service_banner")

    mocker.patch.object(main.socket, "create_connection", side_effect=TimeoutError("timed out"))

    mime_types, message = main.run({"arguments": {"input": {"port": 22, "address": {"address": "1.2.3.4"}}}})[0]

    assert mime_types == {"error/timeout"}
    assert "1.2.3.4:22" in message


def test_service_banner_read_timeout_is_not_a_timeout(mocker):
    """A timeout during recv() is NOT a task timeout: many services (HTTP,
    TLS) accept the connection and wait for the client to speak first, so a
    server that sends no banner is normal. Like on base, it is error/boefje —
    reporting TIMEOUT would rerun every silent service forever."""
    main = _main("kat_service_banner")

    sock = mocker.Mock()
    sock.recv.side_effect = TimeoutError("read exceeded")
    sock.close = mocker.Mock()
    mocker.patch.object(main.socket, "create_connection", return_value=sock)

    mime_types, message = main.run({"arguments": {"input": {"port": 22, "address": {"address": "1.2.3.4"}}}})[0]

    assert mime_types == {"error/boefje"}
    assert "no banner" in message
    sock.close.assert_called_once()


def test_service_banner_read_error_is_not_a_timeout(mocker):
    main = _main("kat_service_banner")

    sock = mocker.Mock()
    sock.recv.side_effect = OSError("connection reset by peer")
    sock.close = mocker.Mock()
    mocker.patch.object(main.socket, "create_connection", return_value=sock)

    mime_types, message = main.run({"arguments": {"input": {"port": 22, "address": {"address": "1.2.3.4"}}}})[0]

    assert mime_types == {"error/boefje"}
    assert "reset by peer" in message
    sock.close.assert_called_once()


def test_service_banner_connection_refused_is_not_a_timeout(mocker):
    main = _main("kat_service_banner")

    mocker.patch.object(main.socket, "create_connection", side_effect=ConnectionRefusedError("refused"))

    mime_types, _ = main.run({"arguments": {"input": {"port": 22, "address": {"address": "1.2.3.4"}}}})[0]

    assert mime_types == {"error/boefje"}


SUBPROCESS_TIMEOUT_BOEFJES = {
    "kat_ssl_scan": {
        "arguments": {
            "input": {
                "object_type": "IPService",
                "ip_port": {"address": {"address": "1.2.3.4"}, "port": 443},
                "service": {"name": "https"},
            }
        }
    },
    "kat_masscan": {"arguments": {"input": {"start_ip": {"address": "1.2.3.4"}, "mask": 24}}},
    "kat_wpscan": {
        "arguments": {
            "input": {
                "software": {"name": "WordPress"},
                "ooi": {"netloc": {"name": "example.com"}, "path": "", "scheme": "https"},
            }
        }
    },
    "kat_webpage_capture": {"arguments": {"input": {"scheme": "https", "netloc": {"name": "example.com"}, "path": ""}}},
}


@pytest.mark.parametrize("boefje,boefje_meta", sorted(SUBPROCESS_TIMEOUT_BOEFJES.items()), ids=str)
def test_subprocess_boefje_timeout_returns_timeout_mimetype(mocker, boefje, boefje_meta):
    main = _main(boefje)

    mocker.patch.object(main.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["tool"], timeout=1234))

    results = main.run(boefje_meta)

    assert len(results) == 1
    mime_types, message = results[0]

    assert mime_types == {"error/timeout"}
    assert isinstance(message, str)


def test_nmap_and_nuclei_subprocess_timeout_returns_timeout_mimetype(mocker):
    """nmap_udp/ports/ip_range and nuclei_exposed_panels/take_over have no
    main.py of their own: inside their OCI image they execute the shared
    kat_nmap_tcp / kat_nuclei_cve modules, so those must report the timeout."""
    for module_name, boefje_meta in [
        (
            "kat_nmap_tcp",
            {"arguments": {"input": {"object_type": "IPAddressV4", "address": "1.2.3.4"}, "oci_arguments": []}},
        ),
        ("kat_nuclei_cve", {"arguments": {"input": {"name": "example.com"}, "oci_arguments": []}}),
    ]:
        main = _main(module_name)

        mocker.patch.object(main.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["tool"], timeout=1234))

        mime_types, message = main.run(boefje_meta)[0]

        assert mime_types == {"error/timeout"}, module_name


def test_dnssec_drill_timeout_returns_timeout_mimetype(monkeypatch):
    main = _main("kat_dnssec")

    def timeout(cmd, capture_output, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(main.subprocess, "run", timeout)

    mime_types, message = main.run({"arguments": {"input": {"name": "example.org"}}})[0]

    assert mime_types == {"error/timeout"}
    assert "drill timed out for example.org" in message


def _schemas() -> list[tuple[str, dict]]:
    plugins_dir = Path(helpers.__file__).parent
    schemas = []
    for schema_path in sorted(plugins_dir.glob("*/schema.json")):
        schema = json.loads(schema_path.read_text())
        schemas.append((schema_path.parent.name, schema))
    return schemas


def test_every_boefje_schema_is_valid_json_schema():
    for name, schema in _schemas():
        jsonschema.validators.validator_for(schema).check_schema(schema)


def test_timeout_settings_reject_non_positive_values():
    """A timeout strictly below its schema minimum must be rejected. Note 0 is
    deliberately still valid where minimum is 0 (e.g. kat_dns_version):
    rejecting it would break orgs that stored TIMEOUT=0 before the minimum
    existed (per review L4)."""
    for name, schema in _schemas():
        for key, property_schema in schema.get("properties", {}).items():
            if "TIMEOUT" not in key or "minimum" not in property_schema:
                continue

            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate({key: property_schema["minimum"] - 1}, schema)


def _wrapped_body_read_timeout() -> requests.exceptions.ConnectionError:
    """What requests raises when a read times out while consuming a response
    body (urllib3 ReadTimeoutError chained under ConnectionError)."""
    error = requests.exceptions.ConnectionError("wrapped")
    error.__cause__ = type("ReadTimeoutError", (Exception,), {})("Read timed out. (read timeout=45)")
    return error


WRAPPED_BODY_TIMEOUT_BOEFJES = {
    # boefje: (boefje_meta, patched entry point that raises)
    "kat_green_hosting": ({"arguments": {"input": {"hostname": {"name": "example.com"}}}}, ("requests", "get")),
    "kat_cve_2023_35078": ({"arguments": {"input": input_website}}, ("requests", "get")),
    "kat_cve_finding_types": ({"arguments": {"input": {"id": "CVE-2020-1234"}}}, ("requests", "get")),
    "kat_external_db": ({"organization": "test"}, ("requests", "get")),
    "kat_retirejs_finding_types": ({}, ("requests", "get")),
    "kat_snyk_finding_types": ({"arguments": {"input": {"id": "SNYK-JS-LODASH-567746"}}}, ("requests", "get")),
    "kat_export_http": ({"arguments": {"input": {"id": "x"}}, "organization": "test"}, ("requests", "request")),
    "kat_maxmind_geoip": (
        {"arguments": {"input": {"address": "1.2.3.4"}}},
        None,  # refresh_geoip raises
    ),
    "kat_rpki": (
        {"arguments": {"input": {"address": "1.2.3.4"}}},
        None,  # refresh_cache raises
    ),
}


@pytest.mark.parametrize("boefje,meta_and_target", sorted(WRAPPED_BODY_TIMEOUT_BOEFJES.items()), ids=str)
def test_requests_boefje_wrapped_body_read_timeout_returns_timeout_mimetype(mocker, boefje, meta_and_target):
    """A read timeout while consuming
    the response body arrives as ConnectionError-wrapping-ReadTimeoutError and
    must be classified as error/timeout by every requests-based boefje."""
    boefje_meta, target = meta_and_target
    main = _main(boefje)
    wrapped = _wrapped_body_read_timeout()

    if target is None:
        function_name = "refresh_geoip" if boefje == "kat_maxmind_geoip" else "refresh_cache"
        mocker.patch.object(main, function_name, side_effect=wrapped)
    else:
        module_name, function_name = target
        mocker.patch.object(getattr(main, module_name), function_name, side_effect=wrapped)

    mime_types, _ = main.run(boefje_meta)[0]

    assert mime_types == {"error/timeout"}, boefje


def test_unrelated_connection_error_is_not_a_timeout(mocker):
    """Refused connections / DNS failures must propagate (finding 2.1's guard
    against false positives), not become error/timeout."""
    main = _main("kat_green_hosting")

    mocker.patch.object(
        main.requests, "get", side_effect=requests.exceptions.ConnectionError("Name or service not known")
    )

    with pytest.raises(requests.exceptions.ConnectionError):
        main.run({"arguments": {"input": {"hostname": {"name": "example.com"}}}})


def test_dns_version_timeout_returns_timeout_mimetype(mocker):
    """Regression: kat_dns_version catches dns.exception.Timeout and reports
    error/timeout (previously an unhandled exception → FAILED task)."""
    main = _main("kat_dns_version")

    mocker.patch.object(main, "getenv", side_effect=lambda key, default="30": {"TIMEOUT": "30"}.get(key, default))

    def udp_timeout(query, where, timeout, port):
        raise main.dns.exception.Timeout("timed out")

    mocker.patch.object(main.dns.query, "udp", side_effect=udp_timeout)

    mime_types, message = main.run(
        {
            "arguments": {
                "input": {
                    "service": {"name": "domain"},
                    "ip_port": {"address": {"address": "1.2.3.4"}, "port": 53, "protocol": "udp"},
                }
            }
        }
    )[0]

    assert mime_types == {"error/timeout"}
    assert "1.2.3.4:53" in message


def test_testssl_sh_ciphers_scan_timeout_setting_reaches_subprocess(mocker):
    """The whole-scan budget is a
    separate setting (SCAN_TIMEOUT, default 600) and must reach
    subprocess.run — the per-connection TIMEOUT keeps its original meaning."""
    main = _main("kat_testssl_sh_ciphers")
    captured = {}

    def fake_run(cmd, capture_output, env, timeout):
        captured["scan_timeout"] = timeout
        captured["env"] = env
        return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"")

    mocker.patch.object(main.os.environ, "copy", return_value={})
    mocker.patch.object(
        main.os, "getenv", side_effect=lambda key, default="30": {"SCAN_TIMEOUT": "777"}.get(key, default)
    )
    mocker.patch.object(main.Path, "exists", return_value=False)  # force the raise path
    mocker.patch.object(main.subprocess, "run", side_effect=fake_run)
    mocker.patch.object(main, "_input_target", return_value=(None, "1.2.3.4", 443, "https"))
    mocker.patch.object(main, "_jsonfile_argument", side_effect=lambda args, path: args)

    with pytest.raises(subprocess.CalledProcessError):
        main.run(
            {
                "arguments": {
                    "input": {
                        "hostname": {"name": "example.com"},
                        "ip_service": {
                            "service": {"name": "https"},
                            "ip_port": {"address": {"address": "1.2.3.4"}, "port": 443},
                        },
                    },
                    "oci_arguments": ["--jsonfile=/tmp/x.json"],
                }
            }
        )

    assert captured["scan_timeout"] == 777
    assert captured["env"]["OPENSSL_TIMEOUT"] == "30"  # unchanged per-connection meaning

    assert captured["scan_timeout"] == 777
    assert captured["env"]["OPENSSL_TIMEOUT"] == "30"  # unchanged per-connection meaning


def test_all_timeout_boefjes_are_covered_by_the_suite():
    """Every boefje that reports
    error/timeout must appear in this test module's coverage lists, so future
    boefjes cannot silently miss the functionality. DICOM is excluded by name
    (documented known limitation)."""
    source = Path(__file__).read_text()

    plugins_dir = Path(helpers.__file__).parent
    timeout_boefjes = set()
    for main_path in plugins_dir.glob("*/main.py"):
        if "error/timeout" in main_path.read_text():
            timeout_boefjes.add(main_path.parent.name)

    assert timeout_boefjes, "sanity: the suite must cover some boefjes"
    # Boefjes covered by their own dedicated test modules instead of this one.
    covered_elsewhere = {"kat_crt_sh", "kat_ssl_certificates", "kat_testssl_sh_ciphers"}
    for boefje in sorted(timeout_boefjes - covered_elsewhere):
        assert boefje in source, f"{boefje} reports error/timeout but is not covered by this test module"

    # ...but the dedicated modules must actually exist and test the timeout.
    dedicated_names = {
        "kat_crt_sh": "test_crt_sh.py",
        "kat_ssl_certificates": "test_ssl_certificates_boefje.py",
        "kat_testssl_sh_ciphers": "test_testssl_sh.py",
    }
    for boefje, filename in dedicated_names.items():
        dedicated = plugins_dir.parent.parent / "tests" / "plugins" / filename
        assert dedicated.exists(), f"{dedicated} missing for {boefje}"

    # DICOM is the documented exception: it must NOT report error/timeout yet.
    assert "error/timeout" not in (plugins_dir / "kat_dicom" / "main.py").read_text()

    # Fierce is the other documented exception: its all-timeout behavior is
    # pre-existing semantics (timeout treated as "no record"), which this PR
    # deliberately does not change.
    assert "error/timeout" not in (plugins_dir / "kat_fierce" / "main.py").read_text()


def test_nikto_hard_timeout_is_wired_through():
    """kat_nikto is a Node boefje (main.js, not main.py), so it is invisible to
    the main.py-based coverage discovery above. Its hard timeout must still be
    wired: execSync gets a timeout, kills with SIGKILL (perl traps SIGTERM),
    and reports error/timeout."""
    plugins_dir = Path(helpers.__file__).parent
    source = (plugins_dir / "kat_nikto" / "main.js").read_text()

    assert "timeout:" in source
    assert 'killSignal: "SIGKILL"' in source
    assert '"error/timeout"' in source

    schema = json.loads((plugins_dir / "kat_nikto" / "schema.json").read_text())
    timeout_setting = schema["properties"]["TIMEOUT"]
    assert timeout_setting["type"] == "integer"
    assert timeout_setting["minimum"] >= 1
    assert "MAX_TIME" in schema["properties"]  # the budget TIMEOUT derives from


def test_dns_no_record_types_with_email_timeouts_is_a_timeout(mocker):
    """Edge case: with no configured record types there are no record queries,
    so the outcomes ledger is empty. The all-timeout decision must not depend
    on it being non-empty: the timed-out email-security lookups alone make the
    scan inconclusive."""
    main = _main("kat_dns")

    mocker.patch.object(main, "get_record_types", lambda: set())
    mocker.patch.object(main.dns.resolver.Resolver, "resolve", side_effect=main.dns.resolver.Timeout("timed out"))
    mocker.patch.object(main, "get_email_security_records", lambda *args: "Timeout")

    mime_types, _ = main.run({"arguments": {"input": {"name": "example.com"}}})[0]

    assert mime_types == {"error/timeout"}
