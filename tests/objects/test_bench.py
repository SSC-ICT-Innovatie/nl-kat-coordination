import contextlib

import pytest
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management.color import no_style
from django.db import connections
from psycopg.errors import FeatureNotSupported

from objects.management.commands.generate_benchmark_data import generate
from objects.models import Hostname, IPAddress, bulk_insert
from objects.views import HostnameDetailView, HostnameListView, IPAddressDetailView, IPAddressListView
from openkat.models import Organization
from plugins.models import Plugin
from tasks.models import ObjectSet, Schedule, Task
from tasks.tasks import recalculate_scan_levels, run_schedule
from tests.conftest import setup_request

# IMPORTANT: one should be careful with using function-scoped database fixtures here that clear xtdb between runs (such
# as "xtdb"), as this breaks the session-scoped database setup in this test file.


@pytest.fixture(scope="session")
def xtdbulk(request: pytest.FixtureRequest, django_db_blocker):
    """session scoped variant of xtdb fixture, so we don't have to seed the database every time (as we only do reads)"""
    objects = apps.get_app_config("objects")
    object_models = list(objects.get_models())
    con = connections["xtdb"]

    xdist_suffix = getattr(request.config, "workerinput", {}).get("workerid")

    for obj in object_models:
        if obj._meta.db_table.startswith("test_"):
            continue
        obj._meta.db_table = f"test_{xdist_suffix}_{obj._meta.db_table}".lower()  # Table names are not case-insensitive

    style = no_style()
    erase = [
        "{} {} {};".format(
            style.SQL_KEYWORD("ERASE"),
            style.SQL_KEYWORD("FROM"),
            style.SQL_FIELD(con.ops.quote_name(obj._meta.db_table)),
        )
        for obj in object_models
    ]

    with django_db_blocker.unblock():
        with contextlib.suppress(FeatureNotSupported):
            con.ensure_connection()
            con.ops.execute_sql_flush(erase)

        yield

        with contextlib.suppress(FeatureNotSupported):
            con.ensure_connection()
            con.ops.execute_sql_flush(erase)


@pytest.fixture(scope="session")
def N():
    return 100_000


@pytest.fixture(scope="session")
def bulk_data_org(xtdbulk, N):
    org, created = Organization.objects.get_or_create(code="testdns", name="testdns")
    (
        hostnames,
        ips,
        ports,
        a_records,
        aaaa_records,
        ns_records,
        mx_records,
        txt_records,
        caa_records,
        findings,
        finding_types,
        software,
    ) = generate(N, 2, 1, include_dns_records=True)
    bulk_insert(hostnames)
    bulk_insert(ips)
    bulk_insert(ports)
    bulk_insert(a_records)
    bulk_insert(aaaa_records)
    bulk_insert(ns_records)
    bulk_insert(mx_records)
    bulk_insert(txt_records)
    bulk_insert(caa_records)
    bulk_insert(findings)
    bulk_insert(finding_types)
    bulk_insert(software)

    return org


@pytest.fixture
def bulk_data(bulk_data_org: Organization):
    bulk_data_org.save()


def test_query_many_hostnames(bulk_data, benchmark):
    def select():
        list(Hostname.objects.select_related("network").filter(name__contains="123"))

    benchmark(select)


def test_query_many_ipaddresses(bulk_data, benchmark):
    def select():
        list(IPAddress.objects.select_related("network").filter(address__contains="192"))

    benchmark(select)


def test_hostname_list_view(bulk_data, rf, superuser, benchmark, N):
    def render_list_view():
        request = setup_request(rf.get("/objects/hostname/"), superuser)
        view = HostnameListView.as_view()
        response = view(request)
        response.render()
        return response

    result = benchmark(render_list_view)
    assert result.status_code == 200


def test_ipaddress_list_view(bulk_data, rf, superuser, benchmark, N):
    def render_list_view():
        request = setup_request(rf.get("/objects/ipaddress/"), superuser)
        view = IPAddressListView.as_view()
        response = view(request)
        response.render()
        return response

    result = benchmark(render_list_view)
    assert result.status_code == 200


def test_hostname_list_view_filtered(bulk_data, rf, superuser, benchmark, N):
    def render_filtered_view():
        request = setup_request(rf.get("/objects/hostname/?name=test"), superuser)
        view = HostnameListView.as_view()
        response = view(request)
        response.render()
        return response

    result = benchmark(render_filtered_view)
    assert result.status_code == 200


def test_ipaddress_list_view_filtered(bulk_data, rf, superuser, benchmark, N):
    def render_filtered_view():
        request = setup_request(rf.get("/objects/ipaddress/?&address=10"), superuser)
        view = IPAddressListView.as_view()
        response = view(request)
        response.render()
        return response

    result = benchmark(render_filtered_view)
    assert result.status_code == 200


def test_hostname_detail_view(bulk_data, rf, benchmark, superuser, N):
    hostname = Hostname.objects.first()

    def render_detail_view():
        request = setup_request(rf.get(f"/objects/hostname/{hostname.pk}/"), superuser)
        view = HostnameDetailView.as_view()
        response = view(request, pk=hostname.pk)
        response.render()
        return response

    result = benchmark(render_detail_view)
    assert result.status_code == 200


def test_ipaddress_detail_view(bulk_data, rf, superuser, benchmark, N):
    ipaddress = IPAddress.objects.first()

    def render_detail_view():
        request = setup_request(rf.get(f"/objects/ipaddress/{ipaddress.pk}/"), superuser)
        view = IPAddressDetailView.as_view()
        response = view(request, pk=ipaddress.pk)
        response.render()
        return response

    result = benchmark(render_detail_view)
    assert result.status_code == 200


def test_object_set(bulk_data, benchmark, N):
    object_set = ObjectSet.objects.create(
        name="Test Set",
        object_type=ContentType.objects.get_for_model(Hostname),
        object_query="dnsnsrecord_nameserver != None",
    )

    def inner():
        return object_set.get_query_objects().count()

    result = benchmark.pedantic(inner, rounds=1)
    assert result == N // 20 - 1


def test_scan_level_recalculation(benchmark, bulk_data, N):
    # The ipaddresses van scan level 1 and all hostnames 2
    benchmark.pedantic(recalculate_scan_levels, rounds=1)  # Subsequent rounds have no updates


def test_task_scheduling_scan_level_filter(bulk_data, docker, celery, benchmark, N):
    plugin = Plugin.objects.create(
        name="test_scan_filter",
        plugin_id="test_scan_filter",
        oci_image="test",
        consumes=["type:hostname"],
        oci_arguments=["bulk"],
        scan_level=2,
        batch_size=500,
    )
    organization = Organization.objects.first()
    plugin.enable_for(organization)
    schedule = Schedule.objects.filter(plugin=plugin, organization=organization).first()

    def inner():
        return run_schedule(schedule, force=True, celery=celery)

    tasks = benchmark(inner)
    assert len(tasks) == N / 500


def test_task_status_check_many_tasks(docker, celery, bulk_data, benchmark, N):
    plugin = Plugin.objects.create(
        name="test_bench",
        plugin_id="test_bench",
        oci_image="test",
        consumes=["type:hostname"],
        oci_arguments=["bulk"],
        scan_level=2,
        batch_size=500,
    )
    organization = Organization.objects.first()
    plugin.enable_for(organization)
    schedule = Schedule.objects.filter(plugin=plugin, organization=organization).first()

    tasks = []
    for i in range(500):
        task = Task(
            organization=organization,
            type="plugin",
            status="queued",
            schedule=schedule,
            data={"plugin_id": plugin.plugin_id, "input_data": [f"test-{i}.com"]},
        )
        tasks.append(task)

    Task.objects.bulk_create(tasks)

    def inner():
        return run_schedule(schedule, force=False, celery=celery)

    result = benchmark.pedantic(inner, rounds=1)
    assert len(result) == N // 500 - 2 or len(result) == N // 500 - 1


def test_task_scheduling_with_object_set_query(bulk_data, docker, celery, benchmark, N):
    plugin = Plugin.objects.create(
        name="query_test",
        plugin_id="query_test",
        oci_image="test",
        consumes=["type:hostname"],
        oci_arguments=["bulk"],
        scan_level=2,
        batch_size=500,
    )
    organization = Organization.objects.first()
    plugin.enable_for(organization)

    schedule = Schedule.objects.filter(plugin=plugin, organization=organization).first()
    schedule.object_set.object_query = 'name ~ "123"'
    schedule.object_set.save()

    def schedule_with_query():
        return run_schedule(schedule, force=True, celery=celery)

    result = benchmark(schedule_with_query)
    how_many_times_is_123_in_1_to_N = len([x for x in range(N) if "123" in str(x)])
    assert len(result) == how_many_times_is_123_in_1_to_N // 500 + 1


def test_count_hostnames_over_time(bulk_data, benchmark, N):
    def inner():
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                SELECT count(*), months from (select _id, extract(month from _valid_from) as months
                from {Hostname._meta.db_table}) as subq group by months""",  # noqa: S608
                {},
            )

    benchmark(inner)
