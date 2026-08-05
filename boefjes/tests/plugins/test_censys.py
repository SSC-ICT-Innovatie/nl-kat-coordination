import json

from boefjes.plugins.kat_censys.normalize import run
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.network import IPPort

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
