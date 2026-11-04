from boefjes.plugins.kat_ssl_scan.normalize import run

INPUT_HOSTNAME_SERVICE = {"object_type": "HostnameIPService", "primary_key": "HostnameIPService|internet|192.0.2.10|tcp|443|https|internet|example.com"}
INPUT_IP_SERVICE = {"object_type": "IPService", "primary_key": "IPService|internet|192.0.2.10|tcp|443|https"}


def _xml(protocols: list[tuple[str, str, bool]], fallback: str | None = None) -> bytes:
    entries = "".join(
        f'<protocol type="{t}" version="{v}" enabled="{1 if e else 0}"/>' for t, v, e in protocols
    )
    fallback_entry = f'<fallback supported="{fallback}"/>' if fallback is not None else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<document><ssltest>'
        f"{entries}{fallback_entry}"
        "</ssltest></document>"
    ).encode()


def _finding_ids(oois) -> set[str]:
    return {str(o.finding_type) for o in oois if o.object_type == "Finding"}


def test_modern_server_raises_nothing():
    protocols = [("ssl", "2", False), ("ssl", "3", False), ("tls", "1.0", False), ("tls", "1.1", False), ("tls", "1.2", True), ("tls", "1.3", True)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols, fallback="1"))) == set()


def test_sslv2_support_raises():
    protocols = [("ssl", "2", True), ("ssl", "3", True), ("tls", "1.2", True), ("tls", "1.3", True)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols))) == {"KATFindingType|KAT-SSL-2-SUPPORT"}


def test_sslv3_without_sslv2_raises_sslv3():
    protocols = [("ssl", "2", False), ("ssl", "3", True), ("tls", "1.2", True), ("tls", "1.3", True)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols))) == {"KATFindingType|KAT-SSL-3-SUPPORT"}


def test_tls10_with_tls11_disabled_raises_tls10():
    protocols = [("tls", "1.0", True), ("tls", "1.1", False), ("tls", "1.2", True), ("tls", "1.3", True)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols))) == {"KATFindingType|KAT-TLS-1.0-SUPPORT"}


def test_tls10_and_tls11_both_enabled_raises_combined():
    protocols = [("tls", "1.0", True), ("tls", "1.1", True), ("tls", "1.2", True), ("tls", "1.3", True)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols))) == {
        "KATFindingType|KAT-TLS-1.0-AND-1.1-SUPPORT"
    }


def test_missing_tls12_raises_no_tls_1_2():
    # The NO-TLS-1.2 finding fires when 1.2 is disabled while 1.0 is still
    # enabled; 1.0-support is checked first by the ladder, so only the
    # NO-TLS finding is new information... the ladder prefers the weaker
    # protocol finding.
    protocols = [("tls", "1.0", True), ("tls", "1.1", False), ("tls", "1.2", False), ("tls", "1.3", True)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols))) == {
        "KATFindingType|KAT-TLS-1.0-SUPPORT"
    }

    # Without 1.0 enabled, the NO-TLS-1.2 finding is reachable.
    protocols = [("tls", "1.1", True), ("tls", "1.2", False), ("tls", "1.3", True)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols))) == {"KATFindingType|KAT-NO-TLS-1.2"}


def test_missing_tls13_alone_raises():
    protocols = [("tls", "1.2", True), ("tls", "1.3", False)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols))) == {"KATFindingType|KAT-NO-TLS-1.3"}


def test_missing_fallback_scsv_raises():
    protocols = [("tls", "1.2", True), ("tls", "1.3", True)]

    assert _finding_ids(run(INPUT_HOSTNAME_SERVICE, _xml(protocols, fallback="0"))) == {
        "KATFindingType|KAT-NO-TLS-FALLBACK-SCSV"
    }


def test_failed_handshake_raises_nothing():
    # A server name the service does not know: the handshake fails, no
    # protocol entries. Not a false positive.
    assert list(run(INPUT_HOSTNAME_SERVICE, b"<document></document>")) == []


def test_findings_bind_to_the_input():
    protocols = [("ssl", "3", True), ("tls", "1.2", True), ("tls", "1.3", True)]

    oois = list(run(INPUT_IP_SERVICE, _xml(protocols)))

    findings = [o for o in oois if o.object_type == "Finding"]
    assert len(findings) == 1
    assert str(findings[0].ooi) == "IPService|internet|192.0.2.10|tcp|443|https"
