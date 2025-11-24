import time
import uuid
from datetime import UTC, datetime

import celery
import structlog
from celery import Celery
from django.conf import settings
from django.core.cache import caches
from django.db import OperationalError, connections
from redis.exceptions import LockError  # type: ignore

from files.models import File
from objects.models import (
    DNSAAAARecord,
    DNSARecord,
    DNSCAARecord,
    DNSCNAMERecord,
    DNSNSRecord,
    DNSTXTRecord,
    Finding,
    FindingOrganization,
    Hostname,
    HostnameOrganization,
    IPAddress,
    IPAddressOrganization,
    IPPort,
    ObjectTask,
    bulk_insert,
)
from openkat.models import Organization, User
from plugins.models import BusinessRule, Plugin
from plugins.plugins.business_rules import (
    ALL_COMMON_TCP,
    COMMON_UDP,
    DB_TCP_PORTS,
    INDICATORS,
    MICROSOFT_RDP_PORTS,
    SA_TCP_PORTS,
    run_rules,
)
from plugins.runner import PluginRunner
from reports.generator import ReportPDFGenerator
from tasks.celery import app
from tasks.models import ObjectSet, Schedule, Task, TaskResult, TaskStatus

logger = structlog.get_logger(__name__)


@app.task(queue=settings.QUEUE_NAME_RECALCULATIONS)
def schedule_scan_profile_recalculations():
    try:
        # Create a Lock to:
        #   1. Avoid running several recalculation scripts at the same time and burn down the database
        #   2. Still take into account that there might be anomalies when a large set of objects has been changed
        with caches["default"].lock(
            "recalculate_scan_levels", blocking=False, timeout=10 * settings.SCAN_LEVEL_RECALCULATION_INTERVAL
        ):
            recalculate_scan_levels()
    except LockError:
        logger.warning("Scan level calculation is running, consider increasing SCAN_LEVEL_RECALCULATION_INTERVAL")


@app.task(queue=settings.QUEUE_NAME_RECALCULATIONS)
def schedule_attribution():
    try:
        with caches["default"].lock(
            "organization_attribution", blocking=False, timeout=10 * settings.ATTRIBUTION_INTERVAL
        ):
            organization_attribution()
    except LockError:
        logger.warning("Organization attribution is running, consider increasing ATTRIBUTION_INTERVAL")


@app.task(queue=settings.QUEUE_NAME_RECALCULATIONS)
def schedule_business_rule_recalculations(from_trigger: bool = False) -> None:
    try:
        # Create a Lock that lives for three times the settings.SCAN_LEVEL_RECALCULATION_INTERVAL at most, to:
        #   1. Avoid running several recalculation scripts at the same time and burn down the database
        #   2. Still take into account that there might be anomalies when a large set of objects has been changed
        with caches["default"].lock(
            "recalculate_business_rules", blocking=False, timeout=10 * settings.BUSINESS_RULE_RECALCULATION_INTERVAL
        ):
            if from_trigger:
                # If a plugin posts hostname updates, this task gets scheduled. But potentially that plugin also posts
                # DNS updates 200ms later. If we run recalculations before that, we miss the DNS updates as the lock
                # makes sure we skip later updates.
                logger.info("Delaying recalculation to potentially fill a batch of updates in one run...")
                time.sleep(5)

            run_rules(BusinessRule.objects.filter(enabled=True), False)
    except LockError:
        if not from_trigger:
            logger.warning(
                "Business rule calculation is running, consider increasing BUSINESS_RULE_RECALCULATION_INTERVAL"
            )
        else:
            logger.debug(
                "Business rule calculation is running, consider increasing BUSINESS_RULE_RECALCULATION_INTERVAL"
            )


@app.task(queue=settings.QUEUE_NAME_RECALCULATIONS)
def run_business_rules(business_rule_ids: list[int]) -> None:
    for business_rule_id in business_rule_ids:
        try:
            business_rule = BusinessRule.objects.get(pk=business_rule_id)
            logger.info("Running business rule: %s", business_rule.name)
            run_rules([business_rule], False)
            logger.info("Completed business rule: %s", business_rule.name)
        except BusinessRule.DoesNotExist:
            logger.error("Business rule %s not found", business_rule_id)
        except Exception:
            logger.exception("Error running business rule %s", business_rule_id)


def recalculate_scan_levels():
    """
    Recalculate scan levels based on DNS relationships:
      - For DNSArecords, sync hostname scan level with IP address scan level (bidirectional)
      - For DNSNSrecords, set the name server's scan level to the hostname's scan level, with a max of 1
      - For DNSCNAMERecords, set the target's scan level to the hostname's scan level

    These updates respect the 'declared' flag - only non-declared scan levels are updated.
    """
    logger.info("Recalculating Scan Profiles...")
    # TODO: when a nameserver inherits L1 and its ips L1 as well, setting the original hostname to L0 will have no
    #   effect since the ip will increase the level to L1..

    # These could create an endless chain, but we just rely on multiple iterations to resolve this.
    sync_cname_scan_levels()
    sync_ns_scan_levels()
    sync_hostname_ip_scan_levels(DNSARecord._meta.db_table)
    sync_hostname_ip_scan_levels(DNSAAAARecord._meta.db_table)

    logger.info("Recalculated Scan Profiles")


def sync_hostname_ip_scan_levels(db_table: str) -> None:
    """
    Synchronize scan levels between hostnames and IP addresses based on DNS A/AAAA records.
    Returns the number of objects updated.
    """
    try:
        with connections["xtdb"].cursor() as cursor:
            # Update IPs where hostname has higher scan level and IP is not declared
            cursor.execute(
                f"""
                INSERT INTO {IPAddress._meta.db_table} (_id, address, network_id, scan_level, declared)
                select target._id, target.address, target.network_id, source.scan_level, false
                FROM {Hostname._meta.db_table} source
                JOIN {db_table} dns on source._id = dns.hostname_id
                JOIN {IPAddress._meta.db_table}
                target ON target._id = dns.ip_address_id
                WHERE source.scan_level IS NOT NULL AND target.declared IS FALSE
                AND (target.scan_level is null or target.scan_level < source.scan_level);
                """  # noqa: S608
            )

            # Update hostnames where IP has higher scan level and hostname is not declared
            cursor.execute(
                f"""
                INSERT INTO {Hostname._meta.db_table} (_id, name, network_id, scan_level, declared)
                select target._id, target.name, target.network_id, source.scan_level, false
                FROM {IPAddress._meta.db_table} source
                JOIN {db_table} dns on source._id = dns.ip_address_id
                JOIN {Hostname._meta.db_table} target ON target._id = dns.hostname_id
                WHERE source.scan_level IS NOT NULL AND target.declared IS FALSE
                AND (target.scan_level is null or target.scan_level < source.scan_level);
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform scan level query", parent_model=Hostname, child_model=IPAddress)


def sync_ns_scan_levels() -> None:
    """
    Sync scan levels to name servers via NS records.
    Name server scan level is set to the hostname's scan level, with a max of 1.
    Returns the number of objects updated.
    """
    try:
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {Hostname._meta.db_table} (_id, name, network_id, root, scan_level, declared)
                select target._id, target.name, target.network_id, target.root, LEAST(source.scan_level, 1), false
                FROM {Hostname._meta.db_table} source
                JOIN {DNSNSRecord._meta.db_table} dns on source._id = dns.hostname_id
                JOIN {Hostname._meta.db_table} target ON target._id = dns.name_server_id
                WHERE source.scan_level IS NOT NULL AND target.declared IS FALSE
                AND (target.scan_level is null or  target.scan_level != LEAST(source.scan_level, 1));
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform NS scan level query")


def sync_cname_scan_levels() -> None:
    """
    Sync scan levels to CNAME targets.
    Target hostname scan level is set to the max of all source hostname scan levels.
    Returns the number of objects updated.
    """
    try:
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {Hostname._meta.db_table} (_id, name, network_id, root, scan_level, declared)
                select target._id, target.name, target.network_id, target.root, source.scan_level, false
                FROM {Hostname._meta.db_table} source
                JOIN {DNSCNAMERecord._meta.db_table} dns on source._id = dns.target_id
                JOIN {Hostname._meta.db_table} target ON target._id = dns.hostname_id
                WHERE source.scan_level IS NOT NULL AND target.declared IS FALSE
                AND target.scan_level is null or  target.scan_level != source.scan_level;
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform CNAME scan level query")


def organization_attribution():
    """
    Attribute through the same models as the scan levels.
    """
    logger.info("Running organization attribution...")

    # TODO: networks?
    attribute_findings()
    attribute_through_cnames()
    attribute_through_ns()
    attribute_through_ip_hostname(DNSARecord._meta.db_table)
    attribute_through_ip_hostname(DNSAAAARecord._meta.db_table)

    logger.info("Finished organization attribution.")


def attribute_findings() -> None:
    try:
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {FindingOrganization._meta.db_table} (_id, finding_id, organization_id)
                SELECT target._id ||'|'|| cast(osource.organization_id as varchar), target._id, osource.organization_id
                FROM {Hostname._meta.db_table} source
                RIGHT JOIN {Finding._meta.db_table} target on source._id = target.hostname_id
                RIGHT JOIN {HostnameOrganization._meta.db_table} osource ON source._id = osource.hostname_id
                LEFT JOIN {FindingOrganization._meta.db_table} otarget ON target._id = otarget.finding_id
                AND osource.organization_id = otarget.organization_id
                WHERE otarget._id is null and osource._id is not null and target._id is not null;
                """  # noqa: S608
            )
            cursor.execute(
                f"""
                INSERT INTO {FindingOrganization._meta.db_table} (_id, finding_id, organization_id)
                SELECT target._id ||'|'|| cast(osource.organization_id as varchar), target._id, osource.organization_id
                FROM {IPAddress._meta.db_table} source
                RIGHT JOIN {Finding._meta.db_table} target on source._id = target.address_id
                RIGHT JOIN {IPAddressOrganization._meta.db_table} osource ON source._id = osource.ipaddress_id
                LEFT JOIN {FindingOrganization._meta.db_table} otarget ON target._id = otarget.finding_id
                AND osource.organization_id = otarget.organization_id
                WHERE otarget._id is null and osource._id is not null and target._id is not null;
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform finding attribution query")


def attribute_through_cnames() -> None:
    try:
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {HostnameOrganization._meta.db_table} (_id, hostname_id, organization_id)
                SELECT target._id ||'|'|| cast(osource.organization_id as varchar), target._id, osource.organization_id
                FROM {Hostname._meta.db_table} source
                RIGHT JOIN {DNSCNAMERecord._meta.db_table} dns on source._id = dns.target_id
                RIGHT JOIN {Hostname._meta.db_table} target ON target._id = dns.hostname_id
                RIGHT JOIN {HostnameOrganization._meta.db_table} osource ON source._id = osource.hostname_id
                LEFT JOIN {HostnameOrganization._meta.db_table} otarget ON target._id = otarget.hostname_id
                AND osource.organization_id = otarget.organization_id
                WHERE otarget._id is null and osource._id is not null and target._id is not null;
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform CNAME scan level query")


def attribute_through_ns() -> None:
    try:
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {HostnameOrganization._meta.db_table} (_id, hostname_id, organization_id)
                SELECT target._id ||'|'|| cast(osource.organization_id as varchar), target._id, osource.organization_id
                FROM {Hostname._meta.db_table} source
                RIGHT JOIN {DNSNSRecord._meta.db_table} dns on source._id = dns.hostname_id
                RIGHT JOIN {Hostname._meta.db_table} target ON target._id = dns.name_server_id
                RIGHT JOIN {HostnameOrganization._meta.db_table} osource ON source._id = osource.hostname_id
                LEFT JOIN {HostnameOrganization._meta.db_table} otarget ON target._id = otarget.hostname_id
                AND osource.organization_id = otarget.organization_id
                WHERE otarget._id is null and osource._id is not null and target._id is not null;
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform CNAME scan level query")


def attribute_through_ip_hostname(db_table: str) -> None:
    try:
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {IPAddressOrganization._meta.db_table} (_id, ipaddress_id, organization_id)
                SELECT target._id ||'|'|| cast(osource.organization_id as varchar), target._id, osource.organization_id
                FROM {Hostname._meta.db_table} source
                RIGHT JOIN {db_table} dns on source._id = dns.hostname_id
                RIGHT JOIN {IPAddress._meta.db_table} target ON target._id = dns.ip_address_id
                RIGHT JOIN {HostnameOrganization._meta.db_table} osource ON source._id = osource.hostname_id
                LEFT JOIN {IPAddressOrganization._meta.db_table} otarget ON target._id = otarget.ipaddress_id
                AND osource.organization_id = otarget.organization_id
                WHERE otarget._id is null and osource._id is not null and target._id is not null;
                """  # noqa: S608
            )
            cursor.execute(
                f"""
                INSERT INTO {HostnameOrganization._meta.db_table} (_id, hostname_id, organization_id)
                SELECT target._id ||'|'|| cast(osource.organization_id as varchar), target._id, osource.organization_id
                FROM {IPAddress._meta.db_table} source
                RIGHT JOIN {db_table} dns on source._id = dns.ip_address_id
                RIGHT JOIN {Hostname._meta.db_table} target ON target._id = dns.hostname_id
                RIGHT JOIN {IPAddressOrganization._meta.db_table} osource ON source._id = osource.ipaddress_id
                LEFT JOIN {HostnameOrganization._meta.db_table} otarget ON target._id = otarget.hostname_id
                AND osource.organization_id = otarget.organization_id
                WHERE otarget._id is null and osource._id is not null and target._id is not null;
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform CNAME scan level query")


@app.task(queue=settings.QUEUE_NAME_SCHEDULE)
def reschedule() -> None:
    logger.info("Scheduling plugins")
    tasks = []

    for schedule in Schedule.objects.filter(enabled=True):
        tasks.extend(run_schedule(schedule, force=False))

    logger.info("Finished scheduling %s plugins", len(tasks))


def run_schedule(schedule: Schedule, force: bool = True, celery: Celery = app) -> list[Task]:
    # Handle report tasks differently from plugin tasks
    if schedule.task_type == "report":
        return run_report_schedule(schedule, force, celery=celery)

    if not schedule.plugin:
        logger.debug("No plugin defined for schedule, skipping")
        return []

    return run_schedule_for_organization(schedule, schedule.organization, force, celery=celery)


def run_report_schedule(schedule: Schedule, force: bool = True, celery: Celery = app) -> list[Task]:
    now = datetime.now(UTC)

    # Check if we need to run based on recurrence rules
    if not force and schedule.recurrences:
        last_run = Task.objects.filter(schedule=schedule, type="report").order_by("-created_at").first()
        if last_run and not schedule.recurrences.between(last_run.created_at, now):
            logger.debug("Report schedule '%s' has already run recently", schedule.id)
            return []

    if schedule.organization:
        organization_codes = [schedule.organization.code]
    else:
        # If no specific organization, generate report for all organizations
        organization_codes = list(Organization.objects.values_list("code", flat=True))

    # Run the report task
    task = run_report_task(
        name=schedule.report_name or f"Scheduled Report {schedule.id}",
        description=schedule.report_description,
        organization_codes=organization_codes,
        finding_types=schedule.report_finding_types,
        object_set_id=schedule.object_set.id if schedule.object_set else None,
        schedule_id=schedule.id,
        celery=celery,
    )

    return [task]


def run_schedule_for_organization(
    schedule: Schedule, organization: Organization | None, force: bool = True, celery: Celery = app
) -> list[Task]:
    now = datetime.now(UTC)
    code = None if organization is None else organization.code

    if not schedule.object_set:
        if force:
            return run_plugin_task(schedule.plugin.plugin_id, code, None, schedule.pk, celery=celery)

        last_run = Task.objects.filter(schedule=schedule, data__input_data=None).order_by("-created_at").first()
        if last_run and not schedule.recurrences.between(last_run.created_at, now):
            logger.debug("Plugin '%s' has already run recently", schedule.plugin.plugin_id)
            return []

        return run_plugin_task(schedule.plugin.plugin_id, code, None, schedule.pk, celery=celery)

    input_data: set[str] = set()
    object_pks = schedule.object_set.traverse_objects(scan_level__gte=schedule.plugin.scan_level)
    if object_pks:
        model_class = schedule.object_set.object_type.model_class()
        model_qs = model_class.objects.filter(pk__in=object_pks)
        input_data = input_data.union([str(model) for model in model_qs if str(model)])

    if not input_data:
        return []

    if force:
        return run_plugin_task(schedule.plugin.plugin_id, code, input_data, schedule.pk, celery=celery)

    # Filter on the schedule and created after the previous occurrence
    last_runs = Task.objects.filter(
        schedule=schedule, created_at__gt=schedule.recurrences.before(now), data__plugin_id=schedule.plugin.plugin_id
    )

    if input_data:
        for targets in last_runs.values_list("data__input_data", flat=True):
            input_data -= set(targets)

    if not input_data:
        return []

    return run_plugin_task(schedule.plugin.plugin_id, code, input_data, schedule.pk, celery=celery)


def run_plugin_on_object_set(
    object_set: ObjectSet, plugin: Plugin, organization: Organization | None, force: bool = True, celery: Celery = app
) -> list[Task]:
    now = datetime.now(UTC)
    code = None if organization is None else organization.code

    input_data: set[str] = set()
    object_pks = object_set.traverse_objects(scan_level__gte=plugin.scan_level)
    if object_pks:
        model_class = object_set.object_type.model_class()
        model_qs = model_class.objects.filter(pk__in=object_pks)
        input_data = input_data.union([str(model) for model in model_qs if str(model)])

    if not input_data:
        return []

    if force or not plugin.recurrences:
        return run_plugin_task(plugin.plugin_id, code, input_data, None, celery=celery)

    # Filter on the schedule and created after the previous occurrence
    last_runs = Task.objects.filter(created_at__gt=plugin.recurrences.before(now), data__plugin_id=plugin.plugin_id)

    if input_data:
        for targets in last_runs.values_list("data__input_data", flat=True):
            input_data -= set(targets)

    if not input_data:
        return []

    return run_plugin_task(plugin.plugin_id, code, input_data, None, celery=celery)


def rerun_task(task: Task, celery: Celery = app) -> list[Task]:
    # Handle different task types
    if task.type == "report":
        # Import here to avoid circular imports

        # Rerun report task with same parameters
        return [
            run_report_task(
                name=task.data.get("name", "Rerun Report"),
                description=task.data.get("description", ""),
                organization_codes=task.data.get("organization_codes", []),
                finding_types=task.data.get("finding_types", []),
                object_set_id=task.data.get("object_set_id"),
            )
        ]
    else:
        # Handle plugin tasks
        plugin = Plugin.objects.get(plugin_id=task.data["plugin_id"])

        return run_plugin_task(
            plugin.plugin_id,
            task.organization.code if task.organization else None,
            task.data["input_data"],
            None,
            celery=celery,
        )


def run_plugin_task(
    plugin_id: str,
    organization_code: str | None = None,
    input_data: str | list[str] | set[str] | None = None,
    schedule_id: int | None = None,
    batch: bool = True,
    celery: Celery = app,
) -> list[Task]:
    inputs: list[str] | None = None

    if isinstance(input_data, set):
        inputs = list(input_data)
    elif isinstance(input_data, str):
        inputs = [input_data]
    else:
        inputs = input_data

    # Get plugin to check for plugin-specific batch_size
    try:
        plugin = Plugin.objects.get(plugin_id=plugin_id)
        # Use plugin-specific batch_size if set, otherwise fall back to global setting
        batch_size = plugin.batch_size if plugin.batch_size is not None else settings.BATCH_SIZE
    except Plugin.DoesNotExist:
        # Fall back to global setting if plugin not found
        batch_size = settings.BATCH_SIZE

    if batch and isinstance(inputs, list) and batch_size > 0 and len(inputs) > batch_size:
        tasks = []
        idx = 0

        for idx_2 in range(batch_size, len(inputs) + batch_size, batch_size):
            tasks.append(
                run_plugin_task(
                    plugin_id, organization_code, inputs[idx:idx_2], schedule_id, batch=False, celery=celery
                )[0]
            )
            idx = idx_2

        logger.info("Created %s batched tasks of batch size %s", len(tasks), batch_size)
        return tasks

    task_id = uuid.uuid4()
    task = Task.objects.create(
        id=task_id,
        type="plugin",
        schedule_id=schedule_id,
        organization=Organization.objects.get(code=organization_code) if organization_code else None,
        status=TaskStatus.QUEUED,
        data={"plugin_id": plugin_id, "input_data": inputs},  # TODO
    )

    run_plugin.bind(celery)  # Make sure to bind the right celery instance to be able to test these tasks.
    async_result = run_plugin.apply_async((plugin_id, organization_code, inputs), task_id=str(task_id))
    task._async_result = async_result

    return [task]


@app.task(bind=True)
def run_plugin(
    self: celery.Task, plugin_id: str, organization_code: str | None = None, input_data: list[str] | None = None
) -> str:
    logger.debug(
        "Starting plugin task",
        task_id=self.request.id,
        organization=organization_code,
        plugin_id=plugin_id,
        input_data=input_data,
    )

    organization: Organization | None = None
    task = Task.objects.get(id=self.request.id)

    if task.status == TaskStatus.CANCELLED:
        raise RuntimeError("Trying to run cancelled task")

    if organization_code:
        organization = Organization.objects.get(code=organization_code)

    plugin = Plugin.objects.filter(plugin_id=plugin_id).first()

    if not plugin:
        task.status = TaskStatus.FAILED
        task.save()
        raise RuntimeError(f"Plugin {plugin_id} not found")

    task.status = TaskStatus.RUNNING
    task.save()

    try:
        out = PluginRunner().run(plugin_id, input_data, task_id=task.pk)

        task.status = TaskStatus.COMPLETED
        task.ended_at = datetime.now(UTC)
        task.save()
    except Exception as e:
        logger.error("Plugin failed: %s", str(e))
        task.refresh_from_db(fields=["status"])

        if task.status != TaskStatus.CANCELLED:
            task.status = TaskStatus.FAILED

        task.ended_at = datetime.now(UTC)
        task.save()
        raise
    finally:
        process_result_task(task.pk, self._app)  # type: ignore[attr-defined]
    logger.info("Handled plugin", organization=organization, plugin_id=plugin_id, input_data=input_data)
    return out


def process_result_task(task_id: uuid.UUID, celery: Celery = app) -> None:
    process_result.bind(celery)
    process_result.apply_async((task_id,))


@app.task
def process_result(task_id: uuid.UUID) -> None:
    """
    What if tasks partially fail? This might create false-positives or skip findings. However, in general it is only
    possible from within the plugin to tell for which input the task has failed, except when it is not being run
    in parallel. But we believe that every openkat installation should aim to have close to zero task failures. If tasks
    regularly fail, this should be handled in the plugin or the batch size should be decreased.

    When that's not possible, we still have the periodic database-wide queries that should clean up the stale data due
    to the failure. It might be worth triggering a run_business_rules task here if the task status is FAILED, but we
    omit that for now.
    """
    task = Task.objects.get(pk=task_id)
    plugin_id = task.data.get("plugin_id")
    PLUGIN_MAPPING = {
        "dns": process_dns,
        "parse-nmap": process_port_scan,
        "parse-nuclei-detection": process_software_scan,
    }

    if plugin_id not in PLUGIN_MAPPING:
        return

    PLUGIN_MAPPING[plugin_id](task)


def process_dns(task: Task) -> None:
    """
    Trigger-based business rule for:
        - missing_spf
        - ipv6_webserver
        - ipv6_nameserver
        - missing_caa
        - missing_dmarc
        - domain_owner_verification
    """
    logger.info("Processing DNS task %s", task.pk)

    enabled_rules = set(BusinessRule.objects.filter(enabled=True).values_list("name", flat=True))
    inputs = Hostname.objects.filter(name__in=task.data["input_data"]).values(
        "pk", "name", "network_id", "root", "dnsnsrecord_nameserver"
    )
    output_objs = ObjectTask.objects.filter(task_id=str(task.pk)).values("output_object", "output_object_type")
    records = {}

    # Parse the DNSRecords into objects using the natural keys. This doesn't require no database access.
    for rec_type in [DNSTXTRecord, DNSCAARecord, DNSAAAARecord, DNSNSRecord]:
        name = str(rec_type.__name__).lower()
        records[name] = [
            rec_type.from_natural_key(obj["output_object"]) for obj in output_objs if obj["output_object_type"] == name
        ]

    input_hostname_pks = {h["pk"] for h in inputs}

    findings = []

    if "missing_spf" in enabled_rules:
        hostnames_with_spf = {
            t.hostname.natural_key for t in records["dnstxtrecord"] if t.value.lower().startswith("v=spf1")
        }
        hostnames_without_spf = input_hostname_pks - hostnames_with_spf

        if hostnames_with_spf:
            Finding.objects.filter(finding_type="KAT-NO-SPF", hostname_id__in=hostnames_with_spf).delete()

        findings.extend([Finding(finding_type_id="KAT-NO-SPF", hostname_id=host) for host in hostnames_without_spf])

    if "missing_caa" in enabled_rules:
        hostnames_with_caa = {caa.hostname.natural_key for caa in records["dnscaarecord"]}
        hostnames_without_caa = input_hostname_pks - hostnames_with_caa

        if hostnames_with_caa:
            Finding.objects.filter(finding_type="KAT-NO-CAA", hostname_id__in=hostnames_with_caa).delete()
        findings.extend([Finding(finding_type_id="KAT-NO-CAA", hostname_id=host) for host in hostnames_without_caa])

    if "ipv6_webservers" in enabled_rules:
        hostnames_with_ipv6 = {txt.hostname.natural_key for txt in records["dnsaaaarecord"]}
        hostnames_without_ipv6 = {h["pk"] for h in inputs if h["dnsnsrecord_nameserver"] is None} - hostnames_with_ipv6

        if hostnames_with_ipv6:
            Finding.objects.filter(
                finding_type_id="KAT-WEBSERVER-NO-IPV6", hostname_id__in=hostnames_with_ipv6
            ).delete()
        findings.extend(
            [Finding(finding_type_id="KAT-WEBSERVER-NO-IPV6", hostname_id=host) for host in hostnames_without_ipv6]
        )

    if "ipv6_nameservers" in enabled_rules:
        hostnames_with_ipv6 = {txt.hostname.natural_key for txt in records["dnsaaaarecord"]}
        ns_hostnames_without_ipv6 = {
            h["pk"] for h in inputs if h["dnsnsrecord_nameserver"] is not None
        } - hostnames_with_ipv6

        if hostnames_with_ipv6:
            Finding.objects.filter(
                finding_type_id="KAT-NAMESERVER-NO-IPV6", hostname_id__in=hostnames_with_ipv6
            ).delete()
        findings.extend(
            [Finding(finding_type_id="KAT-NAMESERVER-NO-IPV6", hostname_id=host) for host in ns_hostnames_without_ipv6]
        )

    if "domain_owner_verification" in enabled_rules:
        hostnames_with_ownership_pending = {
            txt.hostname.natural_key for txt in records["dnsnsrecord"] if txt.name_server.name in INDICATORS
        }
        hostnames_without_ownership_pending = input_hostname_pks - hostnames_with_ownership_pending

        if hostnames_without_ownership_pending:
            Finding.objects.filter(
                finding_type="KAT-DOMAIN-OWNERSHIP-PENDING", hostname_id__in=hostnames_without_ownership_pending
            ).delete()
        findings.extend(
            [
                Finding(finding_type_id="KAT-DOMAIN-OWNERSHIP-PENDING", hostname_id=host)
                for host in hostnames_with_ownership_pending
            ]
        )

    if "missing_dmarc" in enabled_rules:
        with_dmarc = {
            txt.hostname.natural_key
            for txt in records["dnstxtrecord"]
            if txt.prefix == "_dmarc" and txt.value.lower().startswith("v=dmarc1")
        }
        nonroot_hostnames_without_dmarc = {h["name"] for h in inputs if h["pk"] not in with_dmarc or not h["root"]}

        if nonroot_hostnames_without_dmarc:
            # TODO: we should filter the network as well later on
            name_filter = " or ".join(
                [f"POSITION(h.name IN '{hostname}') != 0" for hostname in nonroot_hostnames_without_dmarc]
            )
            root_hostnames_with_dmarc = {
                h.name
                for h in Hostname.objects.raw(f"""
                    SELECT h._id, h.name, h.network_id, h.root, h.declared, h.scan_level
                    FROM {Hostname._meta.db_table} h
                    INNER JOIN {DNSTXTRecord._meta.db_table} txt ON h._id = txt.hostname_id
                    WHERE txt.prefix = '_dmarc' AND UPPER(txt.value::text) LIKE UPPER('v=dmarc1%%') AND root = true
                    AND ({name_filter})
                """)  # noqa: S608
            }
            with_root_dmarc = {
                host["pk"] for host in inputs if any(root in host["name"] for root in root_hostnames_with_dmarc)
            }
        else:
            with_root_dmarc = set()

        if with_dmarc | with_root_dmarc:
            Finding.objects.filter(finding_type="KAT-NO-DMARC", hostname_id__in=with_dmarc | with_root_dmarc).delete()

        hostnames_without_dmarc = input_hostname_pks - (with_dmarc | with_root_dmarc)
        findings.extend([Finding(finding_type_id="KAT-NO-DMARC", hostname_id=host) for host in hostnames_without_dmarc])

    if findings:
        bulk_insert(findings)

    logger.info("Finished processing DNS task %s", task.pk)


def process_port_scan(task: Task) -> None:
    """
    Trigger-based business rule for:
        - open_sysadmin_port
        - open_database_port
        - open_remote_desktop_port
        - open_uncommon_port
        - open_common_port
    """
    logger.info("Processing port scan %s", task.pk)

    # Check which business rules are enabled
    enabled_rules = set(BusinessRule.objects.filter(enabled=True).values_list("name", flat=True))

    inputs = IPAddress.objects.filter(address__in=task.data["input_data"]).values("pk")
    output_objs = ObjectTask.objects.filter(task_id=str(task.pk)).values("output_object", "output_object_type")
    ports = [IPPort.from_natural_key(o["output_object"]) for o in output_objs if o["output_object_type"] == "ipport"]
    input_ip_pks = {ip["pk"] for ip in inputs}
    findings = []

    if "open_sysadmin_port" in enabled_rules:
        ips_with_sysadmin_port = {port.address.natural_key for port in ports if port.port in SA_TCP_PORTS}
        ips_without_sysadmin_port = input_ip_pks - ips_with_sysadmin_port
        Finding.objects.filter(finding_type="KAT-OPEN-SYSADMIN-PORT", address_id__in=ips_without_sysadmin_port).delete()
        findings.extend(
            [Finding(finding_type_id="KAT-OPEN-SYSADMIN-PORT", address_id=ip) for ip in ips_with_sysadmin_port]
        )
    if "open_database_port" in enabled_rules:
        ips_with_database_port = {port.address.natural_key for port in ports if port.port in DB_TCP_PORTS}
        ips_without_database_port = input_ip_pks - ips_with_database_port
        Finding.objects.filter(finding_type="KAT-OPEN-DATABASE-PORT", address_id__in=ips_without_database_port).delete()
        findings.extend(
            [Finding(finding_type_id="KAT-OPEN-DATABASE-PORT", address_id=ip) for ip in ips_with_database_port]
        )
    if "open_remote_desktop_port" in enabled_rules:
        ips_with_rdp_port = {port.address.natural_key for port in ports if port.port in MICROSOFT_RDP_PORTS}
        ips_without_rdp_port = input_ip_pks - ips_with_rdp_port
        Finding.objects.filter(finding_type="KAT-REMOTE-DESKTOP-PORT", address_id__in=ips_without_rdp_port).delete()
        findings.extend([Finding(finding_type_id="KAT-REMOTE-DESKTOP-PORT", address_id=ip) for ip in ips_with_rdp_port])
    if "open_common_port" in enabled_rules:
        ips_with_common_port = {
            port.address.natural_key
            for port in ports
            if (port.protocol == "TCP" and port.port in ALL_COMMON_TCP)
            or (port.protocol == "UDP" and port.port in COMMON_UDP)
        }
        ips_without_common_port = input_ip_pks - ips_with_common_port
        Finding.objects.filter(finding_type="KAT-OPEN-COMMON-PORT", address_id__in=ips_without_common_port).delete()
        findings.extend([Finding(finding_type_id="KAT-OPEN-COMMON-PORT", address_id=ip) for ip in ips_with_common_port])
    if "open_uncommon_port" in enabled_rules:
        ips_with_uncommon_port = {
            port.address.natural_key
            for port in ports
            if (port.protocol == "TCP" and port.port not in ALL_COMMON_TCP)
            or (port.protocol == "UDP" and port.port not in COMMON_UDP)
        }
        ips_without_uncommon_port = input_ip_pks - ips_with_uncommon_port
        Finding.objects.filter(finding_type="KAT-UNCOMMON-OPEN-PORT", address_id__in=ips_without_uncommon_port).delete()
        findings.extend(
            [Finding(finding_type_id="KAT-UNCOMMON-OPEN-PORT", address_id=ip) for ip in ips_with_uncommon_port]
        )

    if findings:
        bulk_insert(findings)

    logger.info("Finished processing port scan task %s", task.pk)


def process_software_scan(task: Task) -> None:
    """
    Trigger-based business rule for:
        - parse-nuclei-detection

    And through this parsing plugin:
        - nuclei-tls-version
        - nuclei-telnet-detect
        - nuclei-rdp-detect
        - nuclei-pgsql-detect
        - nuclei-openssh-detect
        - nuclei-mysql-detect
        - nuclei-mongodb-detect
        - nuclei-ibm-d2b-database-server
    """
    logger.info("Processing software scan %s", task.pk)

    # Check which business rules are enabled
    enabled_rules = set(BusinessRule.objects.filter(enabled=True).values_list("name", flat=True))
    output_objs = ObjectTask.objects.filter(task_id=str(task.pk)).values("output_object", "output_object_type")

    ips = {
        IPAddress.from_natural_key(o["output_object"]) for o in output_objs if o["output_object_type"] == "ipaddress"
    }
    ipports = [IPPort.from_natural_key(o["output_object"]) for o in output_objs if o["output_object_type"] == "ipport"]
    ports_with_software = (
        IPPort.objects.filter(pk__in=[port.natural_key for port in ipports])
        .select_related("address")
        .prefetch_related("software")
        .values("pk", "address", "software__name")
    )
    findings = []

    logger.info("ports: %s", ipports)
    logger.info("pks: %s", [port.natural_key for port in ipports])
    logger.info("software: %s", ports_with_software)

    ips_without_software = ips

    for sw in ["mysql", "mongodb", "openssh", "rdp", "pgsql", "telnet", "db2"]:
        if f"{sw}_detection" in enabled_rules:
            ips_with_sw = {
                port["address"]
                for port in ports_with_software
                if port["software__name"] and port["software__name"].lower() == sw
            }
            ips_without_software -= ips_with_sw
            findings.extend([Finding(finding_type_id="KAT-EXPOSED-SOFTWARE", address_id=ip) for ip in ips_with_sw])

    if ips_without_software:
        Finding.objects.filter(finding_type="KAT-EXPOSED-SOFTWARE", address_id__in=ips_without_software).delete()

    if findings:
        bulk_insert(findings)

    logger.info("Finished processing software scan %s", task.pk)


def process_file(file: File, handle_error: bool = False, celery: Celery = app) -> list[Task]:
    if file.type == "error" and not handle_error:
        logger.info("Raw file %s contains an exception trace and handle_error is set to False. Skipping.", file.pk)
        return []

    tasks = []

    logger.info("Processing Raw file %s", file.pk)

    if hasattr(file, "task_result") and file.task_result is not None:
        organization = file.task_result.task.organization

        for plugin in Plugin.objects.filter(consumes__contains=[f"file:{file.type}"]):
            tasks.extend(
                run_plugin_task(
                    plugin.plugin_id, organization.code if organization else None, str(file.pk), celery=celery
                )
            )

        return tasks

    # For files without a task result, check all organizations with enabled schedules
    for plugin in Plugin.objects.filter(consumes__contains=[f"file:{file.type}"]):
        enabled_orgs = (
            Schedule.objects.filter(plugin=plugin, enabled=True).values_list("organization", flat=True).distinct()
        )

        # Check if there's a global schedule (organization=None)
        has_global_schedule = None in enabled_orgs

        if has_global_schedule:
            # If there's a global schedule, create tasks for all organizations
            for org in Organization.objects.all():
                tasks.extend(run_plugin_task(plugin.plugin_id, org.code, str(file.pk), celery=celery))
        else:
            # Otherwise, only create tasks for specific organizations
            for org_id in enabled_orgs:
                if org_id:
                    org = Organization.objects.get(pk=org_id)
                    tasks.extend(run_plugin_task(plugin.plugin_id, org.code, str(file.pk), celery=celery))

    return tasks


def run_report_task(
    name: str,
    description: str = "",
    organization_codes: list[str] | None = None,
    finding_types: list[str] | None = None,
    object_set_id: int | None = None,
    schedule_id: int | None = None,
    user_id: int | None = None,
    celery: Celery = app,
) -> Task:
    """Create and queue a report generation task"""
    task_id = uuid.uuid4()

    # Get the organization (for single org mode) - use first org if multiple
    organization = None
    if organization_codes and len(organization_codes) > 0:
        organization = Organization.objects.filter(code=organization_codes[0]).first()

    task = Task.objects.create(
        id=task_id,
        type="report",
        schedule_id=schedule_id,
        organization=organization,
        status=TaskStatus.QUEUED,
        data={
            "name": name,
            "description": description,
            "organization_codes": organization_codes or [],
            "finding_types": finding_types or [],
            "object_set_id": object_set_id,
            "user_id": user_id,
        },
    )

    create_report.bind(celery)
    async_result = create_report.apply_async(
        (name, description, organization_codes, finding_types, object_set_id, user_id), task_id=str(task_id)
    )
    task._async_result = async_result

    return task


@app.task(bind=True)
def create_report(
    self: celery.Task,
    name: str,
    description: str = "",
    organization_codes: list[str] | None = None,
    finding_types: list[str] | None = None,
    object_set_id: int | None = None,
    user_id: int | None = None,
) -> str:
    """Celery task for generating a report"""
    logger.info(
        "Starting report generation task", task_id=self.request.id, name=name, organization_codes=organization_codes
    )

    task = Task.objects.get(id=self.request.id)

    if task.status == TaskStatus.CANCELLED:
        raise RuntimeError("Trying to run cancelled task")

    task.status = TaskStatus.RUNNING
    task.save()

    try:
        # Get organizations if codes provided
        organizations = None
        if organization_codes:
            organizations = Organization.objects.filter(code__in=organization_codes)

        # Get object set if provided
        object_set = None
        if object_set_id:
            object_set = ObjectSet.objects.get(id=object_set_id)

        # Get user if provided
        user = None
        if user_id:
            user = User.objects.get(id=user_id)

        # Generate the report
        generator = ReportPDFGenerator(
            name=name,
            description=description,
            organizations=organizations,
            finding_types=finding_types,
            object_set=object_set,
            user=user,
        )
        report = generator.generate_pdf_report()

        # Create TaskResult to link file back to task
        TaskResult.objects.create(task=task, file=report.file)

        task.status = TaskStatus.COMPLETED
        task.ended_at = datetime.now(UTC)
        task.save()

        logger.info("Report generation completed successfully", task_id=self.request.id, report_id=report.id)
        return f"Report generated successfully: {report.id}"

    except Exception as e:
        task.refresh_from_db(fields=["status"])

        if task.status != TaskStatus.CANCELLED:
            task.status = TaskStatus.FAILED

        task.ended_at = datetime.now(UTC)
        task.save()

        logger.exception("Report generation failed", task_id=self.request.id, error=str(e))
        raise
