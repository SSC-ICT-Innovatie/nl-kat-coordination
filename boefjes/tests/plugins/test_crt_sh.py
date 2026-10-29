import json

import pytest
import requests

from boefjes.plugins.kat_crt_sh import main
from boefjes.plugins.kat_crt_sh.normalize import run
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.dns.zone import Hostname

input_ooi = {"hostname": {"name": "example.com"}}


def _raw(common_name: str, name_value: str) -> bytes:
    return json.dumps(
        [
            {
                "common_name": common_name,
                "name_value": name_value,
                "not_before": "2020-01-01T00:00:00",
                "not_after": "2999-01-01T00:00:00",
                "issuer_name": "C=US, O=Example CA",
                "serial_number": "0a1b",
            }
        ]
    ).encode()


def test_crt_sh_normalizer_wildcard_and_email_identities_do_not_crash():
    # crt.sh name_value routinely contains wildcard and email identities. These
    # are not valid Hostnames; before the fix a single one raised a
    # ValidationError that aborted the run and dropped every hostname and
    # certificate of the scan.
    raw = _raw("*.example.com", "*.example.com\nexample.com\nadmin@example.com\nwww.example.com")

    oois = list(run(input_ooi, raw))

    hostname_names = {o.name for o in oois if isinstance(o, Hostname)}
    # Wildcard is stripped to the bare domain, the plain names survive, and no
    # invalid identity (containing '*' or '@') leaks through.
    assert hostname_names == {"example.com", "www.example.com"}
    # The certificate itself is still yielded.
    assert any(isinstance(o, X509Certificate) for o in oois)


def test_crt_sh_normalizer_only_invalid_identities_still_yields_certificate():
    raw = _raw("*.example.com", "*.example.com\nsupport@example.com")

    oois = list(run(input_ooi, raw))

    # The wildcard collapses onto example.com; the email is skipped; the cert survives.
    assert {o.name for o in oois if isinstance(o, Hostname)} == {"example.com"}
    assert any(isinstance(o, X509Certificate) for o in oois)


@pytest.mark.parametrize(
    "exception",
    [requests.exceptions.ConnectTimeout("Connection timed out"), requests.exceptions.ReadTimeout("Read timed out")],
)
def test_crt_sh_timeout_returns_timeout(mocker, exception):
    mocker.patch.object(main, "request_certs", side_effect=exception)

    boefje_meta = {"arguments": {"input": {"hostname": {"name": "example.com"}}}}

    results = main.run(boefje_meta)

    assert len(results) == 1

    mime_types, content = results[0]

    assert mime_types == {"error/timeout"}
    assert "crt.sh timed out for example.com" in content


def test_crt_sh_success_returns_normal_result(mocker):
    mocker.patch.object(main, "request_certs", return_value="[]")

    boefje_meta = {"arguments": {"input": {"hostname": {"name": "example.com"}}}}

    assert main.run(boefje_meta) == [(set(), "[]")]


def test_crt_sh_request_uses_default_connect_and_read_timeout(mocker):
    get = mocker.patch.object(main.requests, "get")
    get.return_value.status_code = 200
    get.return_value.json.return_value = []

    main.request_certs("example.com")

    assert get.call_args.kwargs["timeout"] == (main.CONNECT_TIMEOUT, main.READ_TIMEOUT)


def test_crt_sh_request_uses_configured_connect_and_read_timeout(mocker, monkeypatch):
    monkeypatch.setenv("CONNECT_TIMEOUT", "7")
    monkeypatch.setenv("READ_TIMEOUT", "45")

    get = mocker.patch.object(main.requests, "get")
    get.return_value.status_code = 200
    get.return_value.json.return_value = []

    main.request_certs("example.com")

    assert get.call_args.kwargs["timeout"] == (7, 45)


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.SSLError("certificate verify failed"),
        requests.exceptions.ConnectionError("Name or service not known"),
    ],
)
def test_crt_sh_connection_failure_is_not_reported_as_timeout(mocker, exception):
    mocker.patch.object(main, "request_certs", side_effect=exception)

    boefje_meta = {"arguments": {"input": {"hostname": {"name": "example.com"}}}}

    with pytest.raises(type(exception)):
        main.run(boefje_meta)
