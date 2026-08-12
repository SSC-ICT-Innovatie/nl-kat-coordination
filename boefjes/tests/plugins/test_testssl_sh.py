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
                "key_size": 253,
                "bits": 256,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "x1302",
            },
            {
                "cipher_suite_alias": "TLS_CHACHA20_POLY1305_SHA256",
                "encryption_algorithm": "ChaCha20",
                "cipher_suite_name": "TLS_CHACHA20_POLY1305_SHA256",
                "key_size": 253,
                "bits": 256,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "x1303",
            },
            {
                "cipher_suite_alias": "TLS_AES_128_GCM_SHA256",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "TLS_AES_128_GCM_SHA256",
                "key_size": 253,
                "bits": 128,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "x1301",
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
            },
            {
                "cipher_suite_alias": "TLS_DHE_RSA_WITH_AES_256_GCM_SHA384",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "DHE-RSA-AES256-GCM-SHA384",
                "key_size": 2048,
                "bits": 256,
                "key_exchange_algorithm": "DH",
                "cipher_suite_code": "x9f",
            },
            {
                "cipher_suite_alias": "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
                "encryption_algorithm": "ChaCha20",
                "cipher_suite_name": "ECDHE-RSA-CHACHA20-POLY1305",
                "key_size": 521,
                "bits": 256,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "xcca8",
            },
            {
                "cipher_suite_alias": "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "ECDHE-RSA-AES128-GCM-SHA256",
                "key_size": 521,
                "bits": 128,
                "key_exchange_algorithm": "ECDH",
                "cipher_suite_code": "xc02f",
            },
            {
                "cipher_suite_alias": "TLS_DHE_RSA_WITH_AES_128_GCM_SHA256",
                "encryption_algorithm": "AESGCM",
                "cipher_suite_name": "DHE-RSA-AES128-GCM-SHA256",
                "key_size": 2048,
                "bits": 128,
                "key_exchange_algorithm": "DH",
                "cipher_suite_code": "x9e",
            },
        ],
    }
    assert len(oois) == 1
    assert oois[0].suites == expected_suites
