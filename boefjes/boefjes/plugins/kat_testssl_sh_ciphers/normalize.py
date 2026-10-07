import json
import re
from collections.abc import Iterable
from typing import Any

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.service import TLSCipher

CIPHER_ID_RE = re.compile(r"^cipher-tls1[_-](?P<version>[0-9_]+)_(?P<code>.+)$", re.IGNORECASE)
CIPHER_CODE_RE = re.compile(r"^x[0-9a-f]+$", re.IGNORECASE)


def _protocol_from_id(cipher_id: str) -> str | None:
    match = CIPHER_ID_RE.match(cipher_id)
    if not match:
        return None
    return f"TLSv1.{match.group('version').replace('_', '.')}"


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
    """Parse one structured testssl JSON cipher finding.

    testssl's JSON envelope is structured, but the cipher-specific fields are
    still encoded in its `finding` value. We deliberately use the JSON `id`
    to identify the protocol and cipher code, and validate the finding shape
    instead of relying on unguarded positional indexing.
    """
    cipher_id = cipher.get("id", "")
    protocol = _protocol_from_id(cipher_id)
    finding = cipher.get("finding")
    if not protocol or not isinstance(finding, str):
        return None

    parts = finding.split()
    if len(parts) < 7:
        return None

    # The first fields are stable across testssl 3.2.x JSON output:
    # protocol, hex code, IANA/OpenSSL name, key exchange, ...
    if not CIPHER_CODE_RE.match(parts[1]):
        return None

    if parts[0] != protocol:
        # Keep the explicit JSON id as the source of protocol truth.
        parts = [protocol, *parts[1:]]

    suite: dict[str, Any] = {
        "cipher_suite_code": parts[1],
        "cipher_suite_name": parts[2],
        "key_exchange_algorithm": parts[3],
    }

    if parts[4].isdigit():
        # TLS <= 1.2 reports a key-exchange/key-size strength before the bulk
        # encryption algorithm. TLS 1.3 does not have an equivalent cipher-suite
        # key exchange strength field.
        if protocol != "TLSv1.3":
            suite["key_exchange_bits"] = int(parts[4])
        encryption_index = 5
        bits_index = 6
        alias_index = 7
    else:
        encryption_index = 4
        bits_index = 5
        alias_index = 6

    if len(parts) <= alias_index or not parts[bits_index].isdigit():
        return None

    encryption = parts[encryption_index]
    suite.update(
        {
            "encryption_algorithm": encryption,
            "encryption_bits": int(parts[bits_index]),
            "cipher_suite_alias": parts[alias_index],
            "characteristics": _characteristics(parts[2], parts[3], encryption),
        }
    )
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
