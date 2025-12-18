from time import sleep

import celery
import celery.result
import pytest
from django.core.files.base import ContentFile

from files.models import File
from objects.models import Hostname, IPAddress, Network
from openkat.models import Organization
from plugins.models import Plugin
from plugins.runner import PluginRunner
from plugins.sync import sync
from tasks.models import Schedule, Task
from tasks.tasks import process_file


@pytest.mark.django_db(transaction=True)
def test_hello_world():
    plugin = Plugin.objects.create(
        name="testing plugins", plugin_id="test", oci_image="hello-world:linux", oci_arguments=["/hello"]
    )

    hello_world = PluginRunner().run(plugin.plugin_id, None, output="-")
    assert "Hello from Docker!" in hello_world
    assert File.objects.count() == 0

    new_out = PluginRunner().run(plugin.plugin_id, None)
    assert "Upload completed. Server responded with: 201 Created" in new_out

    assert File.objects.count() == 1
    file = File.objects.first()
    assert file.file.read().decode() == hello_world


# todo: todo and fix everything below


@pytest.mark.django_db(transaction=True)
def test_input_output():
    plugin = Plugin.objects.create(
        name="Test Plugin", plugin_id="cat-plugin", oci_image="alpine:latest", oci_arguments=["/bin/cat"]
    )

    output = PluginRunner().run(plugin.plugin_id, "hello world^C", output="-")
    assert output == "hello world^C"
    assert File.objects.count() == 0


# test write to stdout
# - also results in 1 (temp) file


@pytest.mark.django_db(transaction=True)
def test_with_static_file_input():
    file = File.objects.create(file=ContentFile("test content", "test.txt"), type="txt")
    plugin = Plugin.objects.create(
        name="Cat File Plugin",
        plugin_id="cat-file-plugin",
        oci_image="alpine:latest",
        oci_arguments=["/bin/cat", "{file/" + str(file.pk) + "}"],
    )

    output = PluginRunner().run(plugin.plugin_id, None, output="-")
    assert output == "test content"


@pytest.mark.django_db(transaction=True)
def test_with_multiple_file_inputs():
    f1 = File.objects.create(file=ContentFile("first\n", "f1.txt"), type="txt")
    f2 = File.objects.create(file=ContentFile("second\n", "f2.txt"), type="txt")

    plugin = Plugin.objects.create(
        name="Cat Two Files",
        plugin_id="cat-two-files",
        oci_image="alpine:latest",
        oci_arguments=["/bin/cat", "{file/" + str(f1.pk) + "}", "{file/" + str(f2.pk) + "}"],
    )

    output = PluginRunner().run(plugin.plugin_id, None, output="-")
    assert output == "first\nsecond\n"


@pytest.mark.django_db(transaction=True)
def test_with_multiple_file_inputs_file_output():
    f1 = File.objects.create(file=ContentFile("first\n", "f1.txt"), type="txt")
    f2 = File.objects.create(file=ContentFile("second\n", "f2.txt"), type="txt")

    plugin = Plugin.objects.create(
        name="Cat Two Files (file output)",
        plugin_id="cat-two-files-file-out",
        oci_image="alpine:latest",
        oci_arguments=["/bin/cat", "{file/" + str(f1.pk) + "}", "{file/" + str(f2.pk) + "}"],
    )

    result = PluginRunner().run(plugin.plugin_id, None)
    assert "Upload completed. Server responded with: 201 Created" in result

    # find the output file by partial name (input files are also present)
    out_files = File.objects.filter(file__contains="cat-two-files-file-out/stdout")
    assert out_files.exists()
    out_file = out_files.first()
    assert out_file.file.read().decode() == "first\nsecond\n"


@pytest.mark.django_db(transaction=True)
def test_argument_with_spaces_is_preserved():
    plugin = Plugin.objects.create(
        name="Echo Plugin",
        plugin_id="echo-plugin",
        oci_image="alpine:latest",
        oci_arguments=["/bin/echo", "{hostname}"],
    )

    output = PluginRunner().run(plugin.plugin_id, ["a b c"], output="-")
    assert output.strip() == "a b c"


@pytest.mark.django_db(transaction=True)
def test_with_argument():
    plugin = Plugin.objects.create(
        name="DNS Plugin",
        plugin_id="nslookup-plugin",
        oci_image="alpine:latest",
        oci_arguments=["nslookup", "{hostname}"],
    )

    output = PluginRunner().run(plugin.plugin_id, ["nu.nl"], output="-")
    assert "Name:	nu.nl" in output


@pytest.mark.django_db(transaction=True)
def test_with_multiple_arguments():
    plugin = Plugin.objects.create(
        name="DNS Plugin",
        plugin_id="nslookup-plugin",
        oci_image="alpine:latest",
        oci_arguments=["nslookup", "{hostname}"],
    )
    output = PluginRunner().run(plugin.plugin_id, ["nu.nl", "example.com"], output="-")
    assert "Name:	nu.nl" in output
    assert "Name:	example.com" in output


def test_plugin_not_found_raises():
    with pytest.raises(Plugin.DoesNotExist):
        PluginRunner().run("non-existent-plugin", None, output="-")


@pytest.mark.django_db(transaction=True)
def test_stderr_is_captured_in_output():
    plugin = Plugin.objects.create(
        name="STDERR Plugin",
        plugin_id="stderr-plugin",
        oci_image="alpine:latest",
        oci_arguments=["sh", "-c", "echo out; echo err 1>&2"],
    )

    output = PluginRunner().run(plugin.plugin_id, None, output="-")
    assert "out" in output
    assert "err" in output


@pytest.mark.django_db(transaction=True)
def test_non_zero_exit_does_not_create_file():
    plugin = Plugin.objects.create(
        name="Failing Plugin",
        plugin_id="failing-plugin",
        oci_image="alpine:latest",
        oci_arguments=["sh", "-c", "echo failing >&2; exit 2"],
    )

    with pytest.raises(Exception):
        PluginRunner().run(plugin.plugin_id, None, output="-")

    assert File.objects.count() == 0


@pytest.mark.django_db(transaction=True, databases=["default", "xtdb"])
def test_process_raw_file_single_task():
    plugin = Plugin.objects.create(
        name="Test Plugin",
        plugin_id="test-process-raw-file",
        oci_image="alpine:latest",
        oci_arguments=["/bin/cat"],
        consumes=["file:txt"],
    )
    file = File.objects.create(file=ContentFile(b"", name="test-file.txt"))

    organization = Organization.objects.create(name="Test")
    Schedule.objects.create(plugin=plugin, enabled=True, organization=organization)

    tasks = process_file(file)
    assert len(tasks) == 1
    assert tasks[0].data["plugin_id"] == plugin.plugin_id
    assert tasks[0].organization == organization


@pytest.mark.django_db(transaction=True, databases=["default", "xtdb"])
def test_worker_dispatches_multiple_plugin_tasks():
    # Two plugins that consume the same file type
    sync()  # Add our local plugins
    plugin1 = Plugin.objects.get(plugin_id="dns")
    plugin2 = Plugin.objects.create(
        name="Reverse Plugin",
        plugin_id="str-reverse",
        oci_image="alpine:latest",
        oci_arguments=["/bin/sh", "-c", "echo {ipaddress} | rev"],
        consumes=["type:IPAddress"],
        scan_level=1,
    )

    # Create input object and schedule
    Hostname.objects.get_or_create(
        name="nu.nl", network=Network.objects.get_or_create(name="internet")[0], scan_level=1
    )

    tasks: list[Task] = []
    plugin_1_schedules = plugin1.schedule()
    plugin_2_schedules = plugin2.schedule()

    for schedule in plugin_1_schedules:
        tasks.extend(schedule.run())

    group_result = celery.result.GroupResult("random-id", results=[task.async_result for task in tasks])
    group_result.join()

    for schedule in plugin_1_schedules:
        schedule.enabled = False  # Avoid running dns again on new hostnames
        schedule.save()

    while Task.objects.count() < 2:
        sleep(1)

    group_result = celery.result.GroupResult(
        "random-id", results=[task.async_result for task in Task.objects.filter(schedule=plugin_2_schedules[0])]
    )
    group_result.join()

    files = {file.file.read().decode().strip()[::-1] for file in File.objects.filter(type="str-reverse")}
    objects = {obj.ip_address for obj in IPAddress.objects.all()}

    assert files == objects


@pytest.mark.django_db(transaction=True, databases=["default", "xtdb"])
def test_worker_dispatches_multiple_plugin_tasks_from_file_input():
    Network.objects.get_or_create(name="internet")
    file = File.objects.create(file=ContentFile("nu.nl\ntweakers.net\n", "hostnames.txt"), type="txt")
    sync()  # Add our local plugins
    plugin = Plugin.objects.get(plugin_id="dns")
    plugin.oci_arguments = ["sh", "-c", "cat {file/" + str(file.pk) + "}" + " | xargs -I {} uv run kat_dns/main.py {}"]
    plugin.consumes = ["file:txt"]
    plugin.save()

    tasks: list[Task] = []
    for schedule in plugin.schedule():
        tasks.extend(schedule.run())

    group_result = celery.result.GroupResult("random-id", results=[task.async_result for task in tasks])
    group_result.join()

    assert File.objects.count() == 2
    assert File.objects.last().task_result.task == tasks[0]


# oci_image = openkat/plugins:latest
# arguments = uv run dns/main.py {hostname} ...
# create hostname with L2
# create schedule for plugin (or plugin.schedule() of plugin.schedule_for(organization))
# wait
# recalculate scan profiles
# wait
# plugin that eats ipaddress


# test with file input ("{file"})
# - create File with pk = 123
# - oci_arguments: "{file/<file.pk>}"
# - run(plugin id, target=None, output="-")

# test with single argument
# - create plugin, with oci_arguments ['curl', 'http://..'] and oci_image=alpine

# test with variable argument
# alpine:latest
# args: ['nslookup', '{hostname}'
# run(plugin id, target=['example.com'], output='-')

# test above with multiple inputs
# run(plugin id, target=['example.com', 'test.com'], output='-')


# alpine:
# ["xargs", "-I", "{}", "-P", "4",  "nslookup", "{}"]
#
# 11:36
#
#
#
# x6019 says:Dan ["example.xom", "
# test.com
# "]
#
# 11:37
#
# x6019 says:
# example.com
#
# test.com
#
