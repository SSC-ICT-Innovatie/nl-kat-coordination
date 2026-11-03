import json
import re
from collections.abc import Iterable
from typing import Any

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.service import TLSCipher

# testssl names its per-protocol cipher findings "cipher-<proto>_<hexcode>", with
# proto one of ssl2, ssl3, tls1 (= TLS 1.0), tls1_1, tls1_2 or tls1_3.
CIPHER_ID_RE = re.compile(r"^cipher-(?P<proto>ssl2|ssl3|tls1(?:_[123])?)_(?P<code>x[0-9a-f]+)$", re.IGNORECASE)
CIPHER_CODE_RE = re.compile(r"^x[0-9a-f]+$", re.IGNORECASE)

PROTOCOL_NAMES = {
    "ssl2": "SSLv2",
    "ssl3": "SSLv3",
    "tls1": "TLSv1",
    "tls1_1": "TLSv1.1",
    "tls1_2": "TLSv1.2",
    "tls1_3": "TLSv1.3",
}

# Encryption strength as testssl prints it: "128", "40,exp" for export-grade
# ciphers, or "None" for NULL ciphers.
BITS_RE = re.compile(r"^(?:(?P<bits>\d+)(?P<export>,exp)?|None)$", re.IGNORECASE)


def _protocol_from_id(cipher_id: str) -> str | None:
    match = CIPHER_ID_RE.match(cipher_id)
    if not match:
        return None
    return PROTOCOL_NAMES[match.group("proto").lower()]


def _characteristics(cipher_suite: str, key_exchange: str, encryption: str) -> list[str]:
    """Expose stable, technology-oriented cipher characteristics for downstream policy Bits."""
    value = f"{cipher_suite} {key_exchange} {encryption}".upper()
    characteristics: list[str] = []
    rules = (
        ("NULL", "NULL"),
        ("RC4", "RC4"),
        ("3DES", "3DES"),
        ("DES-CBC3", "3DES"),
        ("CBC", "CBC"),
        ("EXPORT", "EXPORT"),
        ("ANON", "ANONYMOUS"),
        ("ADH", "ANONYMOUS"),
        ("AECDH", "ANONYMOUS"),
        ("RSA", "RSA"),
    )
    for needle, characteristic in rules:
        if needle in value and characteristic not in characteristics:
            characteristics.append(characteristic)
    if "ECDHE" in value or "DHE" in value:
        characteristics.append("FORWARD_SECRECY")
    return characteristics


def parse_cipher(cipher: dict) -> tuple[str, dict[str, Any]] | None:
    # The protocol is encoded in testssl's cipher ID (e.g. cipher-tls1_2_xc02f).
    cipher_id = cipher.get("id", "")
    protocol = _protocol_from_id(cipher_id)
    finding = cipher.get("finding")

    # Ignore entries that are not recognized cipher records or have no
    # parseable finding string.
    if not protocol or not isinstance(finding, str):
        return None

    # The finding is whitespace-separated. The positions below correspond
    # to testssl's cipher output format.
    parts = finding.split()

    # A cipher finding must contain at least the fields through the alias.
    if len(parts) < 7:
        return None

    # The second field contains the hexadecimal cipher-suite code.
    if not CIPHER_CODE_RE.fullmatch(parts[1]):
        return None

    code = parts[1]
    cipher_suite_name = parts[2]
    key_exchange = parts[3]

    # Older TLS versions include a separate key-size field. TLS 1.3 does not,
    # so the position of the remaining fields depends on whether this value
    # is present.
    if parts[4].isdigit():
        if len(parts) < 8:
            return None

        key_size = int(parts[4])
        encryption = parts[5]
        bits = parts[6]
        alias = parts[7]
    else:
        key_size = None
        encryption = parts[4]
        bits = parts[5]
        alias = parts[6]

    bits_match = BITS_RE.fullmatch(bits)
    if not bits_match:
        return None

    # Export and NULL ciphers are the weakest ones, so they must not be skipped.
    characteristics = _characteristics(cipher_suite_name, key_exchange, encryption)

    if bits_match.group("export") and "EXPORT" not in characteristics:
        characteristics.append("EXPORT")

    suite = {
        "cipher_suite_code": code,
        "cipher_suite_name": cipher_suite_name,
        "key_exchange_algorithm": key_exchange,
        "encryption_algorithm": encryption,
        "encryption_bits": int(bits_match.group("bits") or 0),
        "cipher_suite_alias": alias,
        "characteristics": characteristics,
    }

    # TLS 1.3 does not expose the legacy key-size field, so only retain it
    # for protocols where testssl actually reports one.
    if key_size is not None and protocol != "TLSv1.3":
        suite["key_exchange_bits"] = key_size

    return protocol, suite


def _parse_server_preference(output: list[dict]) -> dict[str, str]:
    preferences: dict[str, str] = {}
    for item in output:
        item_id = item.get("id", "")
        if not item_id.startswith("cipher_order"):
            continue
        finding = item.get("finding")
        if not isinstance(finding, str) or not finding:
            continue
        match = re.search(r"tls1[_-]([23])", item_id, re.IGNORECASE)
        protocol = f"TLSv1.{match.group(1)}" if match else "default"
        preferences[protocol] = finding
    return preferences


def _references(input_ooi: dict) -> tuple[Reference, Reference | None]:
    primary_reference = Reference.from_str(input_ooi["primary_key"])
    if input_ooi.get("object_type") == "HostnameService":
        tokenized = primary_reference.tokenized
        ip_service = tokenized.ip_service
        hostname = tokenized.hostname
        ip_service_reference = Reference.from_str(
            f"IPService|{ip_service.ip_port.address.network.name}|{ip_service.ip_port.address.address}|"
            f"{ip_service.ip_port.protocol}|{ip_service.ip_port.port}|{ip_service.service.name}"
        )
        hostname_reference = Reference.from_str(f"Hostname|{hostname.network.name}|{hostname.name}")
        return ip_service_reference, hostname_reference

    # Backwards compatibility for old IPService normalizer invocations.
    return primary_reference, None


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    ip_service_reference, hostname_reference = _references(input_ooi)
    output = json.loads(raw)
    if not isinstance(output, list):
        raise ValueError("Unexpected testssl JSON: expected an array of findings")

    tls_dict: dict[str, list[dict[str, Any]]] = {}
    for item in output:
        if not isinstance(item, dict):
            continue
        parsed = parse_cipher(item)
        if parsed is None:
            continue
        protocol, suite = parsed
        tls_dict.setdefault(protocol, []).append(suite)

    if tls_dict:
        yield TLSCipher(
            ip_service=ip_service_reference,
            hostname=hostname_reference,
            suites=tls_dict,
            server_preference=_parse_server_preference(output),
        )
