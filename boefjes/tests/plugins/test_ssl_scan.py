import subprocess

from boefjes.plugins.kat_ssl_scan import main

# A minimal sslscan XML document: <ssltest> with protocol entries only
# appears when the connection was established.
XML_BODY = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n<document title="SSLScan Results">'
    b'<ssltest host="192.0.2.10" port="443">'
    b'<protocol type="ssl" version="2" enabled="0"/>'
    b'<protocol type="ssl" version="3" enabled="0"/>'
    b'<protocol type="tls" version="1.0" enabled="0"/>'
    b'<protocol type="tls" version="1.1" enabled="0"/>'
    b'<protocol type="tls" version="1.2" enabled="1"/>'
    b'<protocol type="tls" version="1.3" enabled="1"/>'
    b'<fallback supported="1"/>'
    b"</ssltest></document>"
)


def _meta(input_ooi: dict) -> dict:
    return {"arguments": {"input": input_ooi, "oci_arguments": []}}


def _hostname_service(service: str = "https", ip: str = "192.0.2.10", port: int = 443) -> dict:
    return {
        "object_type": "HostnameIPService",
        "ip_service": {"service": {"name": service}, "ip_port": {"address": {"address": ip}, "port": port}},
        "hostname": {"name": "example.com"},
    }


def _ip_service(service: str = "https", ip: str = "192.0.2.10", port: int = 443) -> dict:
    return {
        "object_type": "IPService",
        "ip_port": {"address": {"address": ip}, "port": port},
        "service": {"name": service},
    }


def test_sni_name_is_one_argv_entry(mocker):
    """sslscan reads the SNI name from the same argv entry as the flag
    (strncmp + offset). Passing it as a separate entry left the name empty
    and silently unscanned."""
    captured = {}

    def fake_run(cmd, capture_output, timeout):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=XML_BODY, stderr=b"")

    mocker.patch.object(main.subprocess, "run", side_effect=fake_run)

    main.run(_meta(_hostname_service()))

    assert "--sni-name=example.com" in captured["cmd"]
    assert "--sni-name" not in captured["cmd"]


def test_ip_service_gets_no_sni_name(mocker):
    captured = {}

    def fake_run(cmd, capture_output, timeout):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=XML_BODY, stderr=b"")

    mocker.patch.object(main.subprocess, "run", side_effect=fake_run)

    main.run(_meta(_ip_service()))

    assert not any(arg.startswith("--sni-name") for arg in captured["cmd"])


def test_target_is_bracketed_address_with_port(mocker):
    captured = {}

    def fake_run(cmd, capture_output, timeout):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=XML_BODY, stderr=b"")

    mocker.patch.object(main.subprocess, "run", side_effect=fake_run)

    main.run(_meta(_hostname_service(ip="2001:db8::1", port=8443)))

    assert captured["cmd"][-1] == "[2001:db8::1]:8443"


def test_starttls_flag_for_starttls_services(mocker):
    captured = {}

    def fake_run(cmd, capture_output, timeout):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=XML_BODY, stderr=b"")

    mocker.patch.object(main.subprocess, "run", side_effect=fake_run)

    main.run(_meta(_hostname_service(service="smtp", port=25)))

    assert "--starttls-smtp" in captured["cmd"]


def test_rdp_flag_for_ms_wbt_server(mocker):
    captured = {}

    def fake_run(cmd, capture_output, timeout):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=XML_BODY, stderr=b"")

    mocker.patch.object(main.subprocess, "run", side_effect=fake_run)

    main.run(_meta(_hostname_service(service="ms-wbt-server", port=3389)))

    assert "--rdp" in captured["cmd"]


def test_non_tls_service_deschedules(mocker):
    output = main.run(_meta(_hostname_service(service="http", port=80)))

    assert output == [({"openkat/deschedule"}, "Skipping check due to non-TLS/STARTTLS service: http")]


def test_success_returns_xml(mocker):
    mocker.patch.object(
        main.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=XML_BODY, stderr=b"")
    )

    mime_types, content = main.run(_meta(_hostname_service()))[0]

    assert mime_types == {"openkat/ssl-scan-output"}
    assert content == XML_BODY.decode()


def test_connection_failure_without_ssltest_is_error_boefje(mocker):
    """sslscan exits 0 even when the connection fails: the missing
    <ssltest> element plus the <error> CDATA is the failure signal."""
    failed = (
        b'<document title="SSLScan Results">'
        b"<error><![CDATA[Could not open a connection to host 192.0.2.10 (Connection refused).]]></error>"
        b"</document>"
    )
    mocker.patch.object(
        main.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=failed, stderr=b"")
    )

    mime_types, content = main.run(_meta(_hostname_service()))[0]

    assert mime_types == {"error/boefje"}
    assert "Connection refused" in content


def test_timeout_returns_error_timeout(mocker):
    error = subprocess.TimeoutExpired(cmd=["sslscan"], timeout=120)
    error.stdout = b"partial"
    mocker.patch.object(main.subprocess, "run", side_effect=error)

    mime_types, content = main.run(_meta(_hostname_service()))[0]

    assert mime_types == {"error/timeout"}
    assert content.startswith("sslscan of [192.0.2.10]:443 timed out after 120s")


def test_nonzero_exit_is_error_boefje(mocker):
    mocker.patch.object(
        main.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"boom")
    )

    mime_types, content = main.run(_meta(_hostname_service()))[0]

    assert mime_types == {"error/boefje"}
    assert "boom" in content
