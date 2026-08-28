import json

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
