from boefjes.plugins.kat_testssl_sh_ciphers.normalize import run
from tests.loading import get_dummy_data

input_ooi = {
    "object_type": "IPService",
    "scan_profile": "scan_profile_type='declared' "
    "reference=Reference('IPService|internet|134.209.85.72|tcp|80|http') level=<ScanLevel.L2: 2>",
    "primary_key": "IPService|internet|134.209.85.72|tcp|80|http",
    "ip_port": {
        "address": {"network": {"name": "internet"}, "address": "134.209.85.72"},
        "protocol": "tcp",
        "port": "80",
    },
    "service": {"name": "http"},
}


def test_cipherless_service():
    oois = list(run(input_ooi, get_dummy_data("inputs/testssl-sh-cipherless.json")))

    # noinspection PyTypeChecker
    expected = []

    assert expected == oois


def test_ciphered_service():
    oois = list(run(input_ooi, get_dummy_data("inputs/testssl-sh-ciphered.json")))

    # noinspection PyTypeChecker
    expected_suites = {
        "TLSv1.3": [
            {
                "cipher_suite_alias": "TLS_AES_256_GCM_SHA384",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "TLS_AES_256_GCM_SHA384",
                "bits": 256,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "x1302",
                "characteristics": [],
            },
            {
                "cipher_suite_alias": "TLS_CHACHA20_POLY1305_SHA256",
                "encryption_algorithm": "ChaCha20",
                "cipher_suite_name": "TLS_CHACHA20_POLY1305_SHA256",
                "bits": 256,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "x1303",
                "characteristics": [],
            },
            {
                "cipher_suite_alias": "TLS_AES_128_GCM_SHA256",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "TLS_AES_128_GCM_SHA256",
                "bits": 128,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "x1301",
                "characteristics": [],
            },
        ],
        "TLSv1.2": [
            {
                "cipher_suite_alias": "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "ECDHE-RSA-AES256-GCM-SHA384",
                "key_size": 521,
                "bits": 256,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "xc030",
                "characteristics": ["RSA", "FORWARD_SECRECY"],
            },
            {
                "cipher_suite_alias": "TLS_DHE_RSA_WITH_AES_256_GCM_SHA384",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "DHE-RSA-AES256-GCM-SHA384",
                "key_size": 2048,
                "bits": 256,
                "key_exchange_algorithm": "DH",
                "cipher_suite_code": "x9f",
                "characteristics": ["RSA", "FORWARD_SECRECY"],
            },
            {
                "cipher_suite_alias": "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
                "encryption_algorithm": "ChaCha20",
                "cipher_suite_name": "ECDHE-RSA-CHACHA20-POLY1305",
                "key_size": 521,
                "bits": 256,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "xcca8",
                "characteristics": ["RSA", "FORWARD_SECRECY"],
            },
            {
                "cipher_suite_alias": "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "ECDHE-RSA-AES128-GCM-SHA256",
                "key_size": 521,
                "bits": 128,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "xc02f",
                "characteristics": ["RSA", "FORWARD_SECRECY"],
            },
            {
                "cipher_suite_alias": "TLS_DHE_RSA_WITH_AES_128_GCM_SHA256",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "DHE-RSA-AES128-GCM-SHA256",
                "key_size": 2048,
                "bits": 128,
                "key_exchange_algorithm": "DH",
                "cipher_suite_code": "x9e",
                "characteristics": ["RSA", "FORWARD_SECRECY"],
            },
        ],
    }
    assert len(oois) == 1
    assert oois[0].suites == expected_suites


def test_ciphered_website_preserves_hostname_in_identity():
    hostname_service_input = {
        "object_type": "HostnameService",
        "primary_key": "HostnameService|internet|192.0.2.10|tcp|443|https|internet|example.com",
        "ip_service": {
            "ip_port": {
                "address": {"network": {"name": "internet"}, "address": "192.0.2.10"},
                "protocol": "tcp",
                "port": "443",
            },
            "service": {"name": "https"},
        },
        "hostname": {"network": {"name": "internet"}, "name": "example.com"},
    }

    oois = list(run(hostname_service_input, get_dummy_data("inputs/testssl-sh-ciphered.json")))

    assert len(oois) == 1
    assert oois[0].hostname.natural_key == "internet|example.com"
    assert oois[0].ip_service.natural_key == "internet|192.0.2.10|tcp|443|https"
    assert oois[0].reference.natural_key == "internet|192.0.2.10|tcp|443|https|internet|example.com"
    assert "TLSv1.3" in oois[0].suites
    assert "key_size" not in oois[0].suites["TLSv1.3"][0]


def test_unknown_cipher_finding_is_ignored_instead_of_crashing():
    raw = b'[{"id":"cipher-tls1_3_x1301","severity":"OK","finding":"TLSv1.3 x1301 TLS_AES_128_GCM_SHA256 ECDH"}]'
    assert list(run(input_ooi, raw)) == []


def test_server_preference_is_preserved():
    raw = (
        b'[{"id":"cipher-tls1_2_xc02f","finding":"TLSv1.2 xc02f '
        b"ECDHE-RSA-AES128-GCM-SHA256 ECDH 521 AESGCM 128 "
        b'TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256"},'
        b'{"id":"cipher_order-tls1_2","finding":"ECDHE-RSA-AES128-GCM-SHA256"}]'
    )
    oois = list(run(input_ooi, raw))
    assert oois[0].server_preference == {"TLSv1.2": "ECDHE-RSA-AES128-GCM-SHA256"}


def test_ciphered_hostname_service_identity_includes_hostname_and_ip_service():
    input_a = {
        "object_type": "HostnameService",
        "primary_key": "HostnameService|internet|192.0.2.10|tcp|443|https|internet|a.example",
    }
    input_b = {
        "object_type": "HostnameService",
        "primary_key": "HostnameService|internet|192.0.2.10|tcp|443|https|internet|b.example",
    }

    cipher_a = list(run(input_a, get_dummy_data("inputs/testssl-sh-ciphered.json")))[0]
    cipher_b = list(run(input_b, get_dummy_data("inputs/testssl-sh-ciphered.json")))[0]

    assert cipher_a.reference.natural_key != cipher_b.reference.natural_key
    assert cipher_a.ip_service.natural_key == cipher_b.ip_service.natural_key
    assert cipher_a.hostname.natural_key == "internet|a.example"
    assert cipher_b.hostname.natural_key == "internet|b.example"


def test_hostname_service_identity_distinguishes_sni_hosts_on_same_ip_service():
    from octopoes.models.ooi.service import HostnameService

    a = HostnameService.from_dict(
        {
            "object_type": "HostnameService",
            "ip_service": "IPService|internet|192.0.2.10|tcp|443|https",
            "hostname": "Hostname|internet|a.example",
        }
    )
    b = HostnameService.from_dict(
        {
            "object_type": "HostnameService",
            "ip_service": "IPService|internet|192.0.2.10|tcp|443|https",
            "hostname": "Hostname|internet|b.example",
        }
    )

    assert a.natural_key != b.natural_key


def test_normalizer_rejects_non_array_json():
    import pytest

    from boefjes.plugins.kat_testssl_sh_ciphers.normalize import run

    with pytest.raises(ValueError, match="expected an array"):
        list(run(input_ooi, b'{"finding":"not-an-array"}'))


def test_normalizer_rejects_malformed_json():
    import pytest

    from boefjes.plugins.kat_testssl_sh_ciphers.normalize import run

    with pytest.raises(ValueError):
        list(run(input_ooi, b"not-json"))


def test_normalizer_ignores_unknown_future_cipher_format():
    from boefjes.plugins.kat_testssl_sh_ciphers.normalize import run

    raw = b"""[
        {"id":"cipher-tls1_3_xffff","finding":"TLSv1.3 xffff future-format"},
        {"id":"unknown-future-record","finding":"future format"}
    ]"""
    assert list(run(input_ooi, raw)) == []


def test_normalizer_marks_weak_cipher_characteristics():
    from boefjes.plugins.kat_testssl_sh_ciphers.normalize import run

    raw = b"""[
        {"id":"cipher-tls1_2_x0010",
        "finding":"TLSv1.2 x0010 ECDHE-RSA-DES-CBC3-SHA ECDH 521 3DES 168 TLS_ECDHE_RSA_WITH_3DES_EDE_CBC_SHA"}
    ]"""
    result = list(run(input_ooi, raw))

    assert result[0].suites["TLSv1.2"][0]["characteristics"] == ["3DES", "CBC", "RSA", "FORWARD_SECRECY"]
