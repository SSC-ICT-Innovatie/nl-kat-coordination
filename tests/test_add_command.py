from io import StringIO

from django.core.management import call_command

from files.models import File
from objects.models import Hostname, IPAddress, Network


def test_add_file_from_path(xtdb, tmp_path):
    out = StringIO()

    f = tmp_path / "tst.txt"
    f.write_text("test content")
    call_command("add", f, stdout=out)

    assert File.objects.count() == 1
    file_obj = File.objects.first()
    assert file_obj.file.read() == b"test content"
    assert "File uploaded successfully" in out.getvalue()
    assert f"ID={file_obj.id}" in out.getvalue()


def test_add_file_from_stdin(xtdb, monkeypatch):
    stdin = StringIO("stdin test data")
    stdin.buffer = stdin
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    out = StringIO()
    call_command("add", stdout=out)

    assert File.objects.count() == 1
    file_obj = File.objects.first()
    assert file_obj.file.read() == b"stdin test data"
    assert "File uploaded successfully" in out.getvalue()


def test_add_single_hostname(xtdb):
    out = StringIO()
    call_command("add", "-H", "test.com", stdout=out)

    assert Hostname.objects.count() == 1
    assert Hostname.objects.filter(name="test.com").exists()
    assert "Created hostname: test.com" in out.getvalue()
    assert "1 created" in out.getvalue()


def test_add_multiple_hostnames_from_stdin(xtdb, monkeypatch):
    stdin = StringIO("test.com\nexample.org\nfoo.bar\n")
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    out = StringIO()
    call_command("add", "-H", stdout=out)

    assert Hostname.objects.count() == 3
    assert Hostname.objects.filter(name="test.com").exists()
    assert Hostname.objects.filter(name="example.org").exists()
    assert Hostname.objects.filter(name="foo.bar").exists()
    assert "3 created" in out.getvalue()


def test_add_hostname_duplicate(xtdb):
    out1 = StringIO()
    call_command("add", "-H", "test.com", stdout=out1)
    assert "Created hostname: test.com" in out1.getvalue()

    # Add again
    out2 = StringIO()
    call_command("add", "-H", "test.com", stdout=out2)
    assert "Hostname already exists: test.com" in out2.getvalue()
    assert "0 created, 1 already existed" in out2.getvalue()
    assert Hostname.objects.count() == 1


def test_add_single_network(xtdb):
    out = StringIO()
    call_command("add", "-N", "10.0.0.0/8", stdout=out)

    # Count without the default "internet" network
    assert Network.objects.filter(name="10.0.0.0/8").exists()
    assert "Created network: 10.0.0.0/8" in out.getvalue()


def test_add_multiple_networks_from_stdin(xtdb, monkeypatch):
    stdin = StringIO("192.168.0.0/16\n10.0.0.0/8\n172.16.0.0/12\n")
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    out = StringIO()
    call_command("add", "-N", stdout=out)

    assert Network.objects.filter(name="192.168.0.0/16").exists()
    assert Network.objects.filter(name="10.0.0.0/8").exists()
    assert Network.objects.filter(name="172.16.0.0/12").exists()
    assert "3 created" in out.getvalue()


def test_add_single_ip(xtdb):
    out = StringIO()
    call_command("add", "-I", "192.168.1.1", stdout=out)

    assert IPAddress.objects.count() == 1
    assert IPAddress.objects.filter(ip_address="192.168.1.1").exists()
    assert "Created IP: 192.168.1.1" in out.getvalue()


def test_add_multiple_ips_from_stdin(xtdb, monkeypatch):
    stdin = StringIO("192.168.1.1\n192.168.1.2\n192.168.1.3\n")
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    out = StringIO()
    call_command("add", "-I", stdout=out)

    assert IPAddress.objects.count() == 3
    assert IPAddress.objects.filter(ip_address="192.168.1.1").exists()
    assert IPAddress.objects.filter(ip_address="192.168.1.2").exists()
    assert IPAddress.objects.filter(ip_address="192.168.1.3").exists()
    assert "3 created" in out.getvalue()


def test_add_with_custom_network_name(xtdb):
    out = StringIO()
    call_command("add", "-H", "test.com", "--network-name", "internal", stdout=out)

    hostname = Hostname.objects.get(name="test.com")
    assert hostname.network.name == "internal"

    out2 = StringIO()
    call_command("add", "-I", "10.0.0.1", "--network-name", "internal", stdout=out2)

    ip = IPAddress.objects.get(ip_address="10.0.0.1")
    assert ip.network.name == "internal"


def test_add_ip_duplicate(xtdb):
    out1 = StringIO()
    call_command("add", "-I", "192.168.1.1", stdout=out1)
    assert "Created IP: 192.168.1.1" in out1.getvalue()

    # Add again
    out2 = StringIO()
    call_command("add", "-I", "192.168.1.1", stdout=out2)
    assert "IP already exists: 192.168.1.1" in out2.getvalue()
    assert "0 created, 1 already existed" in out2.getvalue()
    assert IPAddress.objects.count() == 1


def test_add_multiple_flags_error(xtdb):
    err = StringIO()
    call_command("add", "-H", "test.com", "-N", "10.0.0.0/8", stderr=err)

    assert "Only one of -H, -N, or -I can be specified" in err.getvalue()


def test_add_hostname_empty_stdin_error(xtdb, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    err = StringIO()
    call_command("add", "-H", stderr=err)

    assert "-H flag used without value but stdin is empty" in err.getvalue()


def test_add_network_duplicate(xtdb):
    out1 = StringIO()
    call_command("add", "-N", "192.168.0.0/24", stdout=out1)
    assert "Created network: 192.168.0.0/24" in out1.getvalue()

    # Add again
    out2 = StringIO()
    call_command("add", "-N", "192.168.0.0/24", stdout=out2)
    assert "Network already exists: 192.168.0.0/24" in out2.getvalue()
    assert "0 created, 1 already existed" in out2.getvalue()


def test_add_file_nonexistent_path(xtdb):
    err = StringIO()
    call_command("add", "/nonexistent/file.txt", stderr=err)

    assert "File '/nonexistent/file.txt' not found" in err.getvalue()
    assert File.objects.count() == 0


def test_add_hostnames_with_empty_lines(xtdb, monkeypatch):
    stdin = StringIO("test.com\n\nexample.org\n\n\nfoo.bar\n")
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    out = StringIO()
    call_command("add", "-H", stdout=out)

    assert Hostname.objects.count() == 3
    assert "3 created" in out.getvalue()
