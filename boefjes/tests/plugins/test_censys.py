import json

from boefjes.plugins.kat_censys.normalize import run
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.network import IPPort
from octopoes.models.ooi.service import IPService
from octopoes.models.ooi.software import Software
from octopoes.models.ooi.web import HTTPHeader, IPAddressHTTPURL, Website

input_ooi = {"primary_key": "IPAddressV4|internet|1.2.3.4", "network": {"name": "internet"}}


def _tls_service(leaf_data: dict) -> bytes:
    return json.dumps(
        {
            "ip": "1.2.3.4",
            "services": [
                {
                    "port": 443,
                    "transport_protocol": "TCP",
                    "service_name": "HTTP",
                    "tls": {"certificates": {"leaf_data": leaf_data}},
                }
            ],
        }
    ).encode()


def test_censys_normalizer_tls_without_validity_does_not_crash():
    # Censys frequently omits the certificate validity period. The normalizer
    # used to pass valid_from=0 (an int) into X509Certificate, raising a
    # ValidationError that discarded every OOI already yielded for the host.
    raw = _tls_service(
        {
            "subject_dn": "CN=example.com",
            "issuer_dn": "CN=Example CA",
            "pubkey_algorithm": "RSA",
            "pubkey_bit_size": 2048,
            "fingerprint": "deadbeef",
        }
    )

    oois = list(run(input_ooi, raw))

    # The port and service survive; no malformed certificate is emitted.
    assert any(isinstance(o, IPPort) for o in oois)
    assert not any(isinstance(o, X509Certificate) for o in oois)


def test_censys_normalizer_tls_with_validity_yields_certificate():
    raw = _tls_service(
        {
            "subject_dn": "CN=example.com",
            "issuer_dn": "CN=Example CA",
            "pubkey_algorithm": "RSA",
            "pubkey_bit_size": 2048,
            "fingerprint": "deadbeef",
            "not_before": "2020-01-01T00:00:00Z",
            "not_after": "2999-01-01T00:00:00Z",
        }
    )

    certs = [o for o in run(input_ooi, raw) if isinstance(o, X509Certificate)]

    assert len(certs) == 1
    assert certs[0].valid_from == "2020-01-01T00:00:00Z"
    assert certs[0].valid_until == "2999-01-01T00:00:00Z"
    assert certs[0].serial_number == "deadbeef"


def _http_service(**overrides) -> bytes:
    service = {
        "port": 8443,
        "transport_protocol": "TCP",
        "service_name": "HTTP",
        "software": [
            {
                "product": "nginx",
                "version": "1.18.0",
                "uniform_resource_identifier": "cpe:2.3:a:f5:nginx:1.18.0:*:*:*:*:*:*:*",
            }
        ],
        "http": {
            "request": {"uri": "https://1.2.3.4:8443/"},
            "response": {"headers": {"Server": ["nginx"], "_encoding": ["gzip"]}},
        },
    }
    service.update(overrides)
    return json.dumps({"ip": "1.2.3.4", "services": [service]}).encode()


def test_censys_software_name_is_not_uppercased():
    software = [o for o in run(input_ooi, _http_service()) if isinstance(o, Software)]

    assert len(software) == 1
    assert software[0].name == "nginx"
    assert software[0].version == "1.18.0"
    assert software[0].cpe == "cpe:2.3:a:f5:nginx:1.18.0:*:*:*:*:*:*:*"


def test_censys_http_uses_real_port_and_yields_website_and_ipservice():
    oois = list(run(input_ooi, _http_service()))

    web_urls = [o for o in oois if isinstance(o, IPAddressHTTPURL)]
    assert len(web_urls) == 1
    # The real scanned port (8443), not the fabricated 443/80.
    assert web_urls[0].port == 8443

    assert any(isinstance(o, Website) for o in oois)
    assert any(isinstance(o, IPService) for o in oois)

    headers = {h.key for h in oois if isinstance(h, HTTPHeader)}
    assert "server" in headers
    assert "_encoding" not in headers


def test_censys_quic_service_does_not_crash():
    oois = list(run(input_ooi, _http_service(transport_protocol="QUIC")))

    assert any(isinstance(o, IPAddressHTTPURL) for o in oois)
