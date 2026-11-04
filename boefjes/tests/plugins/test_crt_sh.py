import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jsonschema
import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.x509.oid import NameOID

from boefjes.plugins.kat_crt_sh import main
from boefjes.plugins.kat_crt_sh.normalize import run
from octopoes.models.ooi.certificate import X509CertificateV2
from octopoes.models.ooi.dns.zone import Hostname

input_ooi = {"hostname": {"name": "example.com"}}


def _make_cert(common_name: str = "example.com") -> x509.Certificate:
    """A real self-signed certificate, as crt.sh would serve for /?d=<id>."""
    now = datetime.now(UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, SHA256())
    )


def _entry(common_name: str, name_value: str, pem: str | None = None) -> dict:
    return {
        "common_name": common_name,
        "name_value": name_value,
        "not_before": "2020-01-01T00:00:00",
        "not_after": "2999-01-01T00:00:00",
        "issuer_name": "C=US, O=Example CA",
        "serial_number": "0a1b",
        "id": 12345,
        "pem": pem,
    }


def _raw(entry: dict) -> bytes:
    return json.dumps([entry]).encode()


def test_crt_sh_normalizer_parses_the_downloaded_certificate():
    cert = _make_cert()
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()

    oois = list(run(input_ooi, _raw(_entry("*.example.com", "example.com\nwww.example.com", pem=pem))))

    certificates = [o for o in oois if isinstance(o, X509CertificateV2)]
    assert len(certificates) == 1
    certificate = certificates[0]

    der = cert.public_bytes(serialization.Encoding.DER)
    # Identity is the SHA-256 of the DER — the same key the DER path uses.
    assert certificate.fingerprint == hashlib.sha256(der).hexdigest()
    assert base64.b64decode(certificate.raw) == der
    assert certificate.subject == "CN=example.com"
    assert certificate.issuer == "CN=example.com"
    assert certificate.serial_number == format(cert.serial_number, "x")
    assert certificate.valid_until == cert.not_valid_after_utc.isoformat()
    assert certificate.pk_algorithm == "RSA"
    # The hostnames come from the CT identities, not the certificate.
    assert {o.name for o in oois if isinstance(o, Hostname)} == {"example.com", "www.example.com"}


def test_crt_sh_normalizer_without_pem_yields_no_certificate():
    # Historical entry (or a failed download): hostnames survive, no
    # certificate is emitted — never a placeholder without a fingerprint.
    oois = list(run(input_ooi, _raw(_entry("*.example.com", "*.example.com\nadmin@example.com"))))

    assert not any(isinstance(o, X509CertificateV2) for o in oois)
    assert {o.name for o in oois if isinstance(o, Hostname)} == {"example.com"}


def test_crt_sh_normalizer_wildcard_and_email_identities_do_not_crash():
    # crt.sh name_value routinely contains wildcard and email identities. These
    # are not valid Hostnames; before the fix a single one raised a
    # ValidationError that aborted the run and dropped every hostname and
    # certificate of the scan.
    cert = _make_cert()
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    raw = _raw(_entry("*.example.com", "*.example.com\nexample.com\nadmin@example.com\nwww.example.com", pem=pem))

    oois = list(run(input_ooi, raw))

    hostname_names = {o.name for o in oois if isinstance(o, Hostname)}
    # Wildcard is stripped to the bare domain, the plain names survive, and no
    # invalid identity (containing '*' or '@') leaks through.
    assert hostname_names == {"example.com", "www.example.com"}
    # The certificate itself is still yielded.
    assert any(isinstance(o, X509CertificateV2) for o in oois)


def test_crt_sh_normalizer_only_invalid_identities_still_yields_certificate():
    cert = _make_cert()
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    raw = _raw(_entry("*.example.com", "*.example.com\nsupport@example.com", pem=pem))

    oois = list(run(input_ooi, raw))

    # The wildcard collapses onto example.com; the email is skipped; the cert survives.
    assert {o.name for o in oois if isinstance(o, Hostname)} == {"example.com"}
    assert any(isinstance(o, X509CertificateV2) for o in oois)


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


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.SSLError("certificate verify failed"),
        requests.exceptions.ConnectionError("Name or service not known"),
        requests.exceptions.HTTPError("429 Client Error: Too Many Requests"),
    ],
)
def test_crt_sh_connection_failure_is_reported_as_error_boefje(mocker, exception):
    # Anything that is not a timeout — refused connections, DNS failures,
    # TLS errors, and crt.sh's aggressive 429 rate limiting — is an
    # error/boefje: the reason travels in the raw bytes, no normalizer runs.
    mocker.patch.object(main, "request_certs", side_effect=exception)

    boefje_meta = {"arguments": {"input": {"hostname": {"name": "example.com"}}}}

    results = main.run(boefje_meta)

    assert len(results) == 1
    mime_types, content = results[0]
    assert mime_types == {"error/boefje"}
    assert "crt.sh request failed for example.com" in content


def test_crt_sh_success_returns_normal_result(mocker):
    mocker.patch.object(main, "request_certs", return_value="[]")

    boefje_meta = {"arguments": {"input": {"hostname": {"name": "example.com"}}}}

    assert main.run(boefje_meta) == [(set(), "[]")]


def test_crt_sh_downloads_pem_for_current_entries_only(mocker):
    """The per-certificate download is rate-limited to currently valid
    certificates; historical entries carry no pem and the failed download
    yields None, not a placeholder."""
    mocker.patch.object(
        main,
        "request_certs",
        return_value=json.dumps(
            [
                {"id": 1, "common_name": "example.com", "not_after": "2999-01-01T00:00:00"},
                {"id": 2, "common_name": "example.com", "not_after": "2001-01-01T00:00:00"},
                {"id": 3, "common_name": "example.com", "not_after": "not-a-date"},
            ]
        ),
    )
    download = mocker.patch.object(main, "request_cert", return_value="-----BEGIN CERTIFICATE-----")

    boefje_meta = {"arguments": {"input": {"hostname": {"name": "example.com"}}}}
    _mime_types, content = main.run(boefje_meta)[0]
    entries = json.loads(content)

    download.assert_called_once_with(1)
    assert entries[0]["pem"] == "-----BEGIN CERTIFICATE-----"
    assert entries[1]["pem"] is None
    assert entries[2]["pem"] is None


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


def test_crt_sh_cert_download_uses_the_same_timeouts(mocker, monkeypatch):
    monkeypatch.setenv("CONNECT_TIMEOUT", "3")
    monkeypatch.setenv("READ_TIMEOUT", "9")

    get = mocker.patch.object(main.requests, "get")
    get.return_value.status_code = 200
    get.return_value.text = "-----BEGIN CERTIFICATE-----"

    assert main.request_cert(12345) == "-----BEGIN CERTIFICATE-----"
    assert get.call_args.kwargs["timeout"] == (3, 9)


def test_crt_sh_cert_download_failure_yields_none(mocker):
    get = mocker.patch.object(main.requests, "get", side_effect=requests.exceptions.ConnectionError("boom"))
    assert main.request_cert(12345) is None
    assert get.call_count == 1

    get = mocker.patch.object(main.requests, "get")
    get.return_value.status_code = 429
    assert main.request_cert(12345) is None


@pytest.mark.parametrize("key", ["CONNECT_TIMEOUT", "READ_TIMEOUT"])
@pytest.mark.parametrize("value", [0, -5])
def test_crt_sh_schema_rejects_non_positive_timeouts(key, value):
    schema = json.loads((Path(main.__file__).parent / "schema.json").read_text())

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({key: value}, schema)
