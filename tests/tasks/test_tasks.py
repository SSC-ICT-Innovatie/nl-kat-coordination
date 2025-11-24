from celery import Celery
from django.conf import settings

from files.models import File, GenericContent
from objects.models import (
    DNSAAAARecord,
    DNSNSRecord,
    DNSTXTRecord,
    Finding,
    FindingType,
    Hostname,
    IPAddress,
    IPPort,
    Network,
    ObjectTask,
    Software,
    bulk_insert,
)
from plugins.models import BusinessRule, Plugin
from tasks.models import Schedule, Task, TaskResult, TaskStatus
from tasks.tasks import (
    process_dns,
    process_file,
    process_port_scan,
    process_software_scan,
    run_plugin_task,
    run_schedule,
    run_schedule_for_organization,
)


def test_run_schedule(organization, xtdb, celery: Celery, docker, plugin_container):
    logs = [b"test logs"]
    plugin_container.set_logs(logs)

    plugin = Plugin.objects.create(
        name="test", plugin_id="test", oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )
    plugin.schedule_for(organization)
    schedule = Schedule.objects.filter(plugin=plugin).first()

    assert schedule.object_set.name == "All hostnames"
    assert schedule.object_set.object_query == ""
    assert schedule.plugin == plugin
    assert organization in schedule.plugin.enabled_organizations()

    tasks = run_schedule(schedule, force=False, celery=celery)
    assert len(tasks) == 0
    tasks = run_schedule(schedule, force=True, celery=celery)
    assert len(tasks) == 0

    network = Network.objects.create(name="internet")
    host = Hostname.objects.create(name="test.com", network=network)

    tasks = run_schedule(schedule, force=False, celery=celery)
    assert len(tasks) == 0

    host.scan_level = 2
    host.save()
    tasks = run_schedule(schedule, force=False, celery=celery)
    assert len(tasks) == 1

    assert tasks[0].data == {"input_data": ["test.com"], "plugin_id": "test"}
    assert tasks[0].type == "plugin"
    assert tasks[0].status == TaskStatus.QUEUED
    assert tasks[0].organization == organization
    assert tasks[0].schedule == schedule

    res = tasks[0].async_result.get()
    assert res == logs[0].decode()
    kwargs = docker.containers.create.mock_calls[0].kwargs

    assert kwargs["image"] == "T"
    assert "test_17" in kwargs["name"]
    assert kwargs["command"] == ["test.com"]
    assert kwargs["network"] == settings.DOCKER_NETWORK
    assert kwargs["entrypoint"] == "/plugin/entrypoint"
    assert len(kwargs["volumes"]) == 1
    assert kwargs["volumes"][settings.ENTRYPOINT_VOLUME] == {"bind": "/plugin", "mode": "ro"}
    assert kwargs["environment"]["PLUGIN_ID"] == plugin.plugin_id
    assert kwargs["environment"]["OPENKAT_API"] == f"{settings.OPENKAT_HOST}/api/v1"
    assert kwargs["environment"]["UPLOAD_URL"] == f"{settings.OPENKAT_HOST}/api/v1/file/"
    assert "OPENKAT_TOKEN" in kwargs["environment"]
    assert kwargs["detach"] is True

    plugin2 = Plugin.objects.create(
        name="test2", plugin_id="test2", oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )
    plugin2.schedule()
    schedule = Schedule.objects.filter(plugin=plugin2).first()
    assert schedule.object_set.name == "All hostnames"
    assert schedule.object_set.object_query == ""
    assert schedule.plugin == plugin2
    assert schedule.organization is None
    assert organization in schedule.plugin.enabled_organizations()

    tasks = run_schedule(schedule, celery=celery)
    kwargs = docker.containers.create.mock_calls[5].kwargs
    assert kwargs["environment"]["PLUGIN_ID"] == plugin2.plugin_id

    assert len(tasks) == 1


def test_run_schedule_for_none(xtdb, celery: Celery, organization, docker, plugin_container):
    logs = [b"test logs"]
    plugin_container.set_logs(logs)

    plugin = Plugin.objects.create(
        name="test", plugin_id="test", oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )
    plugin.schedule()
    schedule = Schedule.objects.filter(plugin=plugin).first()

    assert schedule.object_set.name == "All hostnames"
    assert schedule.object_set.object_query == ""
    assert schedule.plugin == plugin

    network = Network.objects.create(name="internet")
    Hostname.objects.create(name="test.com", network=network, scan_level=2)

    tasks = run_schedule(schedule, force=False, celery=celery)
    assert len(tasks) == 1


def test_process_raw_file(xtdb, celery: Celery, organization, organization_b, docker, plugin_container):
    logs = [b"test logs"]
    plugin_container.set_logs(logs)

    plugin = Plugin.objects.create(
        name="test", plugin_id="test", consumes=["file:testfile"], oci_image="T", oci_arguments=["{file}"], scan_level=2
    )
    plugin.schedule()

    f = File.objects.create(file=GenericContent(b"1234"), type="old")
    f.type = "testfile"  # Avoid the process_raw_file signal
    f.save()
    TaskResult.objects.create(file=f, task=Task.objects.create())

    tasks = process_file(f, celery=celery)
    assert len(tasks) == 1
    assert tasks[0].organization is None

    f = File.objects.create(file=GenericContent(b"4321"), type="old")
    f.type = "testfile"  # Avoid the process_raw_file signal
    f.save()
    TaskResult.objects.create(file=f, task=Task.objects.create(organization=organization_b))

    tasks = process_file(f, celery=celery)
    assert len(tasks) == 1
    assert tasks[0].organization == organization_b

    f = File.objects.create(file=GenericContent(b"4321"), type="old")
    f.type = "testfile"  # Avoid the process_raw_file signal
    f.save()

    tasks = process_file(f, celery=celery)
    assert len(tasks) == 2
    assert {task.organization for task in tasks} == {organization, organization_b}
    assert Task.objects.count() == 6


def test_batch_tasks(xtdb, celery: Celery, organization, organization_b, docker, plugin_container):
    logs = [b"test logs"]
    plugin_container.set_logs(logs)

    plugin = Plugin.objects.create(
        name="test", plugin_id="test", oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )
    plugin.schedule()

    network = Network.objects.create(name="internet")

    hns = []
    for i in range(200):
        host = Hostname(name=f"test{i}.com", network=network, scan_level=2)
        hns.append(host)

    bulk_insert(hns)

    tasks = run_plugin_task(plugin.id, organization.code, input_data=[x.name for x in hns], celery=celery)

    assert len(tasks) == 4
    assert len(tasks[0].data["input_data"]) == 50
    assert len(tasks[1].data["input_data"]) == 50
    assert len(tasks[2].data["input_data"]) == 50
    assert len(tasks[3].data["input_data"]) == 50

    # We check previous tasks only when running for a schedule
    tasks = run_plugin_task(plugin.id, organization.code, input_data=[x.name for x in hns], celery=celery)
    assert len(tasks) == 4


def test_batch_scheduled_tasks(xtdb, celery: Celery, organization, organization_b, mocker):
    mocker.patch("tasks.tasks.run_plugin")
    plugin = Plugin.objects.create(
        name="test", plugin_id="test", oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )
    plugin.schedule()
    schedule = Schedule.objects.first()
    network = Network.objects.create(name="internet")

    hns = []
    for i in range(200):
        host = Hostname(name=f"test{i}.com", network=network, scan_level=2)
        hns.append(host)

    bulk_insert(hns)

    tasks = run_schedule_for_organization(schedule, organization, force=False, celery=celery)

    assert len(tasks) == 4
    assert len(tasks[0].data["input_data"]) == 50
    assert len(tasks[1].data["input_data"]) == 50
    assert len(tasks[2].data["input_data"]) == 50
    assert len(tasks[3].data["input_data"]) == 50

    tasks = run_schedule_for_organization(schedule, organization, force=False, celery=celery)
    assert len(tasks) == 0


def test_find_intersecting_input_data(organization):
    data = ["1.com"]
    Task.objects.create(organization=organization, type="plugin", data={"plugin_id": "test", "input_data": data})

    data = ["3.com", "4.com", "5.com"]
    Task.objects.create(organization=organization, type="plugin", data={"plugin_id": "test", "input_data": data})

    data = ["4.com", "5.com"]
    Task.objects.create(organization=organization, type="plugin", data={"plugin_id": "test", "input_data": data})

    # old style vs new style
    target = ["0.com"]
    assert Task.objects.filter(data__input_data__has_any_keys=target).count() == 0

    target = ["1.com"]
    assert Task.objects.filter(data__input_data__has_any_keys=target).count() == 1

    target = ["4.com"]
    assert Task.objects.filter(data__input_data__has_any_keys=target).count() == 2

    target = ["4.com", "5.com"]
    assert Task.objects.filter(data__input_data__has_any_keys=target).count() == 2

    target = ["4.com", "5.com", "6.com"]
    assert Task.objects.filter(data__input_data__has_any_keys=target).count() == 2


def test_process_dns_result(organization, xtdb, task_db):
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")
    ip = IPAddress.objects.create(network=network, address="2001:db8::")

    for code, name in [
        ("KAT-NO-SPF", "missing_spf"),
        ("KAT-WEBSERVER-NO-IPV6", "ipv6_webservers"),
        ("KAT-NAMESERVER-NO-IPV6", "ipv6_nameservers"),
        ("KAT-NO-CAA", "missing_caa"),
        ("KAT-DOMAIN-OWNERSHIP-PENDING", "domain_owner_verification"),
        ("KAT-NO-DMARC", "missing_dmarc"),
    ]:
        BusinessRule.objects.create(name=name, enabled=True)
        FindingType.objects.create(code=code)

    Finding.objects.create(finding_type_id="KAT-NO-SPF", hostname=hn)
    hn2 = Hostname.objects.create(network=network, name="test2.com")
    task_db.data["input_data"] = [str(hn), str(hn2)]
    task_db.save()

    ns = Hostname.objects.create(network=network, name="ns1.registrant-verification.ispapi.net")
    dns_ns = DNSNSRecord.objects.create(hostname=hn, name_server=ns)
    dns_spf = DNSTXTRecord.objects.create(hostname=hn, value="v=spf1 abc def")
    dns_aaaa = DNSAAAARecord.objects.create(hostname=hn, ip_address=ip)
    plugin = Plugin.objects.create(
        name="test", plugin_id=task_db.data["plugin_id"], oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )

    for obj in [hn, ns, dns_ns, dns_spf, dns_aaaa]:
        ObjectTask.objects.create(
            task_id=str(task_db.pk),
            plugin_id=plugin.plugin_id,
            output_object=obj.pk,
            output_object_type=str(obj.__class__.__name__).lower(),
        )

    process_dns(task_db)

    assert Finding.objects.count() == 7
    assert Finding.objects.filter(finding_type_id="KAT-NO-SPF", hostname=hn2).exists()
    assert Finding.objects.filter(finding_type_id="KAT-NO-CAA").count() == 2
    assert Finding.objects.filter(finding_type_id="KAT-NO-CAA", hostname=hn).exists()
    assert Finding.objects.filter(finding_type_id="KAT-NO-CAA", hostname=hn2).exists()
    assert Finding.objects.filter(finding_type_id="KAT-WEBSERVER-NO-IPV6", hostname=hn2).exists()
    assert Finding.objects.filter(finding_type_id="KAT-DOMAIN-OWNERSHIP-PENDING", hostname=hn).exists()
    assert Finding.objects.filter(finding_type_id="KAT-NO-DMARC").count() == 2
    assert Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=hn).exists()
    assert Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=hn2).exists()


def test_process_dns_missing_dmarc(organization, xtdb, task_db):
    network = Network.objects.create(name="test")
    hostname_with_dmarc = Hostname.objects.create(network=network, name="example.com", root=True)
    hostname_without_dmarc = Hostname.objects.create(network=network, name="other.org", root=True)

    BusinessRule.objects.create(name="missing_dmarc", enabled=True)
    FindingType.objects.create(code="KAT-NO-DMARC")
    Finding.objects.create(finding_type_id="KAT-NO-DMARC", hostname=hostname_with_dmarc)

    task_db.data["input_data"] = [str(hostname_with_dmarc), str(hostname_without_dmarc)]
    task_db.save()

    plugin = Plugin.objects.create(
        name="test", plugin_id=task_db.data["plugin_id"], oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )

    dmarc_txt = DNSTXTRecord.objects.create(
        hostname=hostname_with_dmarc, value="v=DMARC1; p=quarantine;", prefix="_dmarc"
    )

    for obj in [hostname_with_dmarc, hostname_without_dmarc, dmarc_txt]:
        ObjectTask.objects.create(
            task_id=str(task_db.pk),
            plugin_id=plugin.plugin_id,
            output_object=obj.pk,
            output_object_type=str(obj.__class__.__name__).lower(),
        )

    process_dns(task_db)

    assert not Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=hostname_with_dmarc).exists()
    assert Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=hostname_without_dmarc).exists()
    assert Finding.objects.filter(finding_type_id="KAT-NO-DMARC").count() == 1


def test_process_dns_missing_dmarc_case_insensitive(organization, xtdb, task_db):
    network = Network.objects.create(name="test")
    hostname = Hostname.objects.create(network=network, name="test.com")

    BusinessRule.objects.create(name="missing_dmarc", enabled=True)
    FindingType.objects.create(code="KAT-NO-DMARC")

    task_db.data["input_data"] = [str(hostname)]
    task_db.save()

    plugin = Plugin.objects.create(
        name="test", plugin_id=task_db.data["plugin_id"], oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )

    for dmarc_value in ["v=dmarc1; p=none;", "V=DMARC1; P=NONE;", "v=DmArC1; p=reject;"]:
        Finding.objects.filter(hostname=hostname).delete()
        dmarc = DNSTXTRecord.objects.create(hostname=hostname, value=dmarc_value, prefix="_dmarc")

        ObjectTask.objects.create(
            task_id=str(task_db.pk),
            plugin_id=plugin.plugin_id,
            output_object=dmarc.pk,
            output_object_type="dnstxtrecord",
        )
        ObjectTask.objects.create(
            task_id=str(task_db.pk),
            plugin_id=plugin.plugin_id,
            output_object=hostname.pk,
            output_object_type="hostname",
        )

        process_dns(task_db)

        assert not Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=hostname).exists()
        dmarc.delete()
        ObjectTask.objects.filter(task_id=str(task_db.pk)).delete()


def test_process_dns_missing_dmarc_root_hostnames(organization, xtdb, task_db):
    network = Network.objects.create(name="test")
    root_with_dmarc = Hostname.objects.create(network=network, name="has-dmarc.com", root=True)
    subdomain_root_dmarc = Hostname.objects.create(network=network, name="mail.has-dmarc.com", root=False)

    root_no_dmarc = Hostname.objects.create(network=network, name="no-dmarc.com", root=True)
    subdomain_no_root_dmarc = Hostname.objects.create(network=network, name="mail.no-dmarc.com", root=False)

    # Second root domain with DMARC, but not an input of the task
    root_with_dmarc_2 = Hostname.objects.create(network=network, name="also-has-dmarc.org", root=True)
    deep = Hostname.objects.create(network=network, name="deep.mail.also-has-dmarc.org", root=False)

    BusinessRule.objects.create(name="missing_dmarc", enabled=True)
    FindingType.objects.create(code="KAT-NO-DMARC")
    Finding.objects.create(finding_type_id="KAT-NO-DMARC", hostname=root_with_dmarc)
    Finding.objects.create(finding_type_id="KAT-NO-DMARC", hostname=subdomain_root_dmarc)
    Finding.objects.create(finding_type_id="KAT-NO-DMARC", hostname=root_with_dmarc_2)
    Finding.objects.create(finding_type_id="KAT-NO-DMARC", hostname=deep)

    task_db.data["input_data"] = [
        str(root_with_dmarc),
        str(subdomain_root_dmarc),
        str(root_no_dmarc),
        str(subdomain_no_root_dmarc),
        str(deep),
    ]
    task_db.save()

    plugin = Plugin.objects.create(
        name="test", plugin_id=task_db.data["plugin_id"], oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )

    dmarc1 = DNSTXTRecord.objects.create(hostname=root_with_dmarc, value="v=DMARC1; p=quarantine;", prefix="_dmarc")
    dmarc2 = DNSTXTRecord.objects.create(hostname=root_with_dmarc_2, value="v=DMARC1; p=reject;", prefix="_dmarc")

    for obj in [root_with_dmarc, subdomain_root_dmarc, root_no_dmarc, subdomain_no_root_dmarc, deep, dmarc1, dmarc2]:
        ObjectTask.objects.create(
            task_id=str(task_db.pk),
            plugin_id=plugin.plugin_id,
            output_object=obj.pk,
            output_object_type=str(obj.__class__.__name__).lower(),
        )

    process_dns(task_db)

    assert not Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=root_with_dmarc).exists()
    assert not Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=root_with_dmarc_2).exists()
    assert not Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=subdomain_root_dmarc).exists()
    assert not Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=deep).exists()

    assert Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=root_no_dmarc).exists()
    assert Finding.objects.filter(finding_type_id="KAT-NO-DMARC", hostname=subdomain_no_root_dmarc).exists()
    assert Finding.objects.filter(finding_type_id="KAT-NO-DMARC").count() == 2


def test_process_port_scan_result(organization, xtdb, task_db):
    network = Network.objects.create(name="test")

    for code, name in [
        ("KAT-OPEN-SYSADMIN-PORT", "open_sysadmin_port"),
        ("KAT-OPEN-DATABASE-PORT", "open_database_port"),
        ("KAT-REMOTE-DESKTOP-PORT", "open_remote_desktop_port"),
        ("KAT-OPEN-COMMON-PORT", "open_common_port"),
        ("KAT-UNCOMMON-OPEN-PORT", "open_uncommon_port"),
    ]:
        FindingType.objects.create(code=code)
        BusinessRule.objects.create(name=name, enabled=True)

    ip1 = IPAddress.objects.create(network=network, address="192.168.1.1")
    ip2 = IPAddress.objects.create(network=network, address="192.168.1.2")
    ip3 = IPAddress.objects.create(network=network, address="192.168.1.3")
    ip4 = IPAddress.objects.create(network=network, address="192.168.1.4")

    finding_type_db = FindingType.objects.get(code="KAT-OPEN-DATABASE-PORT")
    Finding.objects.create(finding_type=finding_type_db, address=ip1)

    task_db.data["plugin_id"] = "nmap"
    task_db.data["input_data"] = [str(ip1), str(ip2), str(ip3), str(ip4)]
    task_db.save()

    port_ssh = IPPort.objects.create(address=ip1, protocol="TCP", port=22)  # Sysadmin port
    port_http = IPPort.objects.create(address=ip1, protocol="TCP", port=80)  # Common port
    port_mysql = IPPort.objects.create(address=ip2, protocol="TCP", port=3306)  # Database port
    port_custom = IPPort.objects.create(address=ip2, protocol="TCP", port=8888)  # Uncommon port
    port_rdp = IPPort.objects.create(address=ip3, protocol="TCP", port=3389)  # RDP port
    port_https = IPPort.objects.create(address=ip4, protocol="TCP", port=443)  # Common port only

    plugin = Plugin.objects.create(name="nmap", plugin_id="nmap", oci_image="T", oci_arguments=["{ip}"], scan_level=2)

    for obj in [port_ssh, port_http, port_mysql, port_custom, port_rdp, port_https]:
        ObjectTask.objects.create(
            task_id=str(task_db.pk),
            plugin_id=plugin.plugin_id,
            output_object=obj.pk,
            output_object_type=str(obj.__class__.__name__).lower(),
        )

    process_port_scan(task_db)

    assert Finding.objects.count() == 8

    assert Finding.objects.filter(finding_type_id="KAT-OPEN-SYSADMIN-PORT", address=ip1).exists()
    assert Finding.objects.filter(finding_type_id="KAT-OPEN-COMMON-PORT", address=ip1).exists()
    assert not Finding.objects.filter(finding_type_id="KAT-OPEN-DATABASE-PORT", address=ip1).exists()

    assert Finding.objects.filter(finding_type_id="KAT-OPEN-DATABASE-PORT", address=ip2).exists()
    assert Finding.objects.filter(finding_type_id="KAT-UNCOMMON-OPEN-PORT", address=ip2).exists()
    assert Finding.objects.filter(finding_type_id="KAT-OPEN-COMMON-PORT", address=ip2).exists()

    assert Finding.objects.filter(finding_type_id="KAT-REMOTE-DESKTOP-PORT", address=ip3).exists()
    assert Finding.objects.filter(finding_type_id="KAT-OPEN-COMMON-PORT", address=ip3).exists()

    assert Finding.objects.filter(finding_type_id="KAT-OPEN-COMMON-PORT", address=ip4).exists()
    assert not Finding.objects.filter(finding_type_id="KAT-UNCOMMON-OPEN-PORT", address=ip4).exists()


def test_process_software_scan_result(organization, xtdb, task_db):
    network = Network.objects.create(name="test")
    FindingType.objects.create(code="KAT-EXPOSED-SOFTWARE")

    for software_name in ["mysql", "mongodb", "openssh", "pgsql"]:
        BusinessRule.objects.create(name=f"{software_name}_detection", enabled=True)

    ip1 = IPAddress.objects.create(network=network, address="192.168.1.1")  # Has MySQL
    ip2 = IPAddress.objects.create(network=network, address="192.168.1.2")  # Has MongoDB and OpenSSH
    ip3 = IPAddress.objects.create(network=network, address="192.168.1.3")  # Has PostgreSQL
    ip4 = IPAddress.objects.create(network=network, address="192.168.1.4")  # No software

    Finding.objects.create(finding_type_id="KAT-EXPOSED-SOFTWARE", address=ip1)

    task_db.data["plugin_id"] = "parse-nuclei-detection"
    task_db.data["input_data"] = [str(ip1), str(ip2), str(ip3), str(ip4)]
    task_db.save()

    mysql = Software.objects.create(name="mysql", version="8.0")
    mongodb = Software.objects.create(name="mongodb", version="5.0")
    openssh = Software.objects.create(name="openssh", version="9.0")
    pgsql = Software.objects.create(name="pgsql", version="14")

    port_mysql = IPPort.objects.create(address=ip1, protocol="TCP", port=3306)
    port_mysql.software.add(mysql)

    port_mongo = IPPort.objects.create(address=ip2, protocol="TCP", port=27017)
    port_mongo.software.add(mongodb)

    port_ssh = IPPort.objects.create(address=ip2, protocol="TCP", port=22)
    port_ssh.software.add(openssh)

    port_pgsql = IPPort.objects.create(address=ip3, protocol="TCP", port=5432)
    port_pgsql.software.add(pgsql)

    port_no_software = IPPort.objects.create(address=ip4, protocol="TCP", port=8080)
    plugin = Plugin.objects.create(
        name="parse-nuclei-detection",
        plugin_id="parse-nuclei-detection",
        oci_image="T",
        oci_arguments=["{ip}"],
        scan_level=2,
    )

    for obj in [ip1, ip2, ip3, ip4, port_mysql, port_mongo, port_ssh, port_pgsql, port_no_software]:
        ObjectTask.objects.create(
            task_id=str(task_db.pk),
            plugin_id=plugin.plugin_id,
            output_object=obj.pk,
            output_object_type=str(obj.__class__.__name__).lower(),
        )

    process_software_scan(task_db)

    assert Finding.objects.filter(finding_type_id="KAT-EXPOSED-SOFTWARE", address=ip1).exists()
    assert Finding.objects.filter(finding_type_id="KAT-EXPOSED-SOFTWARE", address=ip2).exists()
    assert Finding.objects.filter(finding_type_id="KAT-EXPOSED-SOFTWARE", address=ip3).exists()
    assert not Finding.objects.filter(finding_type_id="KAT-EXPOSED-SOFTWARE", address=ip4).exists()

    # Total findings should be 3 because mongodb and openssh on ip2 result in 1 finding on the ip
    assert Finding.objects.filter(finding_type_id="KAT-EXPOSED-SOFTWARE").count() == 3
