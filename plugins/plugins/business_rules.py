import time
from collections.abc import Sequence

import structlog
from django.db import DatabaseError, connections
from django.db.models import Case, Count, F, QuerySet, When
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search

from objects.models import (
    DNSAAAARecord,
    DNSCAARecord,
    DNSNSRecord,
    DNSTXTRecord,
    Finding,
    FindingType,
    Hostname,
    HostnameQLSchema,
    IPAddress,
    IPPort,
    NoOrgQLSchema,
    Software,
    bulk_insert,
)
from plugins.models import BusinessRule
from tasks.models import Task

logger = structlog.get_logger(__name__)


SA_TCP_PORTS = [21, 22, 23, 5900]
DB_TCP_PORTS = [1433, 1434, 3050, 3306, 5432]
MICROSOFT_RDP_PORTS = [3389]
COMMON_TCP_PORTS = [25, 53, 80, 110, 143, 443, 465, 587, 993, 995]
ALL_COMMON_TCP = COMMON_TCP_PORTS + SA_TCP_PORTS + DB_TCP_PORTS + MICROSOFT_RDP_PORTS
COMMON_UDP = [53]
INDICATORS = [
    "ns1.registrant-verification.ispapi.net",
    "ns2.registrant-verification.ispapi.net",
    "ns3.registrant-verification.ispapi.net",
]


def get_rules():
    rules = {
        "invalid_findings": {
            "name": "invalid_findings",
            "description": "Deletes findings with an invalid finding type.",
            "object_type": "hostname",
            "query": "",
            "inverse_query": f"""
             DELETE FROM {Finding._meta.db_table}
             WHERE _id IN (
                 SELECT f._id
                 FROM {Finding._meta.db_table} f
                 LEFT JOIN {FindingType._meta.db_table} ft on f.finding_type_id = ft._id
                 WHERE ft._id IS NULL
             );""",  # noqa: S608
            "finding_type_code": None,
        },
        "ipv6_webservers": {
            "name": "ipv6_webservers",
            "description": "Checks if webserver has IPv6 support",
            "object_type": "hostname",
            "requires": ["dns"],
            "query": f"""
                SELECT distinct h._id, h.name, h.network_id, h.root, h.declared, h.scan_level
                FROM {Hostname._meta.db_table} h
                LEFT JOIN {DNSNSRecord._meta.db_table} ns ON h."_id" = ns."name_server_id"
                LEFT JOIN {DNSAAAARecord._meta.db_table} dns ON dns.hostname_id = h._id
                LEFT JOIN {Finding._meta.db_table} f on (
                    f.hostname_id = h._id and f.finding_type_id = 'KAT-WEBSERVER-NO-IPV6'
                )
                 where f._id is null and dns._id is null and ns._id is null;
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {Hostname._meta.db_table} h ON h._id = f.hostname_id
                    INNER JOIN {DNSAAAARecord._meta.db_table} dns ON dns.hostname_id = h._id
                    LEFT JOIN {DNSNSRecord._meta.db_table} ns ON h."_id" = ns."name_server_id"
                    WHERE ns._id IS NULL AND f.finding_type_id = 'KAT-WEBSERVER-NO-IPV6'
                );""",  # noqa: S608
            "finding_type_code": "KAT-WEBSERVER-NO-IPV6",
        },
        "ipv6_nameservers": {
            "name": "ipv6_nameservers",
            "description": "Checks if nameserver has IPv6 support",
            "object_type": "hostname",
            "requires": ["dns"],
            "query": f"""
                SELECT distinct h._id, h.name, h.network_id, h.root, h.declared, h.scan_level
                FROM {Hostname._meta.db_table} h
                    RIGHT JOIN {DNSNSRecord._meta.db_table} ns ON h."_id" = ns."name_server_id"
                    LEFT JOIN {DNSAAAARecord._meta.db_table} dns ON dns.hostname_id = h._id
                    LEFT JOIN {Finding._meta.db_table} f on (
                        f.hostname_id = h._id and f.finding_type_id = 'KAT-NAMESERVER-NO-IPV6'
                    )
                where f._id is null and dns._id is null;
                 """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {Hostname._meta.db_table} h ON h._id = f.hostname_id
                    INNER JOIN {DNSNSRecord._meta.db_table} ns ON h."_id" = ns."name_server_id"
                    INNER JOIN {DNSAAAARecord._meta.db_table} dns ON dns.hostname_id = h._id
                    WHERE f.finding_type_id = 'KAT-NAMESERVER-NO-IPV6'
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-NAMESERVER-NO-IPV6",
        },
        "missing_spf": {
            "name": "missing_spf",
            "description": "Checks if the hostname has valid SPF records",
            "object_type": "hostname",
            "requires": ["dns"],
            "query": f"""
                SELECT distinct h._id, h.name, h.network_id, h.root, h.declared, h.scan_level
                FROM {Hostname._meta.db_table} h
                         LEFT JOIN {DNSTXTRecord._meta.db_table} dns
                           ON (
                               h."_id" = dns."hostname_id"
                                   AND dns."value"::text LIKE_REGEX 'v=spf1.*' FLAG 'i'
                               )
                     LEFT JOIN {Finding._meta.db_table} f on (
                        f.hostname_id = h._id and f.finding_type_id = 'KAT-NO-SPF'
                     )
                WHERE dns._id IS NULL AND f._id is null;
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {Hostname._meta.db_table} h ON h._id = f.hostname_id
                    INNER JOIN {DNSTXTRecord._meta.db_table} dns ON h."_id" = dns."hostname_id"
                    WHERE dns."value"::text LIKE_REGEX 'v=spf1.*' FLAG 'i'
                    AND f.finding_type_id = 'KAT-NO-SPF'
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-NO-SPF",
        },
        "open_sysadmin_port": {
            "name": "open_sysadmin_port",
            "description": "Detect open sysadmin ports",
            "object_type": "ipaddress",
            "query": f"""
            SELECT distinct ip._id, ip.address, ip.declared, ip.network_id, ip.scan_level
            FROM {IPAddress._meta.db_table} ip
                JOIN {IPPort._meta.db_table} port ON ip."_id" = port.address_id
                LEFT JOIN {Finding._meta.db_table} f on (
                    f.address_id = ip._id and f.finding_type_id = 'KAT-OPEN-SYSADMIN-PORT'
                )
            where f._id is null and port.port in ({", ".join(str(x) for x in SA_TCP_PORTS)});
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {IPAddress._meta.db_table} ip ON ip._id = f.address_id
                    LEFT JOIN {IPPort._meta.db_table} port ON (
                        port.address_id = ip._id AND
                        port.port IN ({", ".join(str(x) for x in SA_TCP_PORTS)})
                    )
                    WHERE port._id IS NULL
                    AND f.finding_type_id = 'KAT-OPEN-SYSADMIN-PORT'
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-OPEN-SYSADMIN-PORT",
        },
        "open_database_port": {
            "name": "open_database_port",
            "description": "Detect open database ports",
            "object_type": "ipaddress",
            "query": f"""
            SELECT distinct ip._id, ip.address, ip.declared, ip.network_id, ip.scan_level
            FROM {IPAddress._meta.db_table} ip
            JOIN {IPPort._meta.db_table} port ON ip."_id" = port.address_id
            LEFT JOIN {Finding._meta.db_table} f on (
                f.address_id = ip._id and f.finding_type_id = 'KAT-OPEN-DATABASE-PORT'
            )
            where f._id is null and port.port in ({", ".join(str(x) for x in DB_TCP_PORTS)});
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {IPAddress._meta.db_table} ip ON ip._id = f.address_id
                    LEFT JOIN {IPPort._meta.db_table} port ON (
                        port.address_id = ip._id AND
                        port.port IN ({", ".join(str(x) for x in DB_TCP_PORTS)})
                    )
                    WHERE f.finding_type_id = 'KAT-OPEN-DATABASE-PORT' AND port._id IS NULL
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-OPEN-DATABASE-PORT",
        },
        "open_remote_desktop_port": {
            "name": "open_remote_desktop_port",
            "description": "Detect open RDP ports",
            "object_type": "ipaddress",
            "query": f"""
            SELECT distinct ip._id, ip.address, ip.declared, ip.network_id, ip.scan_level
            FROM {IPAddress._meta.db_table} ip
                JOIN {IPPort._meta.db_table} port ON ip."_id" = port.address_id
                LEFT JOIN {Finding._meta.db_table} f on (
                    f.address_id = ip._id and f.finding_type_id = 'KAT-REMOTE-DESKTOP-PORT'
                )
            where f._id is null and port.port in ({", ".join(str(x) for x in MICROSOFT_RDP_PORTS)});
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {IPAddress._meta.db_table} ip ON ip._id = f.address_id
                    LEFT JOIN {IPPort._meta.db_table} port ON (
                        port.address_id = ip._id AND
                        port.port IN ({", ".join(str(x) for x in MICROSOFT_RDP_PORTS)})
                    )
                     WHERE f.finding_type_id = 'KAT-REMOTE-DESKTOP-PORT' AND  port._id IS NULL
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-REMOTE-DESKTOP-PORT",
        },
        "open_uncommon_port": {
            "name": "open_uncommon_port",
            "description": "Detect open uncommon ports",
            "object_type": "ipaddress",
            "query": f"""
            SELECT distinct ip._id, ip.address, ip.declared, ip.network_id, ip.scan_level
            FROM {IPAddress._meta.db_table} ip
                JOIN {IPPort._meta.db_table} port ON ip."_id" = port.address_id
                LEFT JOIN {Finding._meta.db_table} f on (
                    f.address_id = ip._id and f.finding_type_id = 'KAT-UNCOMMON-OPEN-PORT'
                )
            where f._id is null and (
                (port.protocol = 'TCP' and port.port not in ({", ".join(str(x) for x in ALL_COMMON_TCP)}))
                or
                (port.protocol = 'UDP' and port.port not in ({", ".join(str(x) for x in COMMON_UDP)}))
            );
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {IPAddress._meta.db_table} ip ON ip._id = f.address_id
                    LEFT JOIN {IPPort._meta.db_table} port ON (
                        port.address_id = ip._id AND
                        (
                            (port.protocol = 'TCP' AND port.port NOT IN ({", ".join(str(x) for x in ALL_COMMON_TCP)}))
                            OR
                            (port.protocol = 'UDP' AND port.port NOT IN ({", ".join(str(x) for x in COMMON_UDP)}))
                        )
                    )
                    WHERE f.finding_type_id = 'KAT-UNCOMMON-OPEN-PORT' AND port._id IS NULL
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-UNCOMMON-OPEN-PORT",
        },
        "open_common_port": {
            "name": "open_common_port",
            "description": "Checks for open common ports",
            "object_type": "ipaddress",
            "query": f"""
            SELECT distinct ip._id, ip.address, ip.declared, ip.network_id, ip.scan_level
            FROM {IPAddress._meta.db_table} ip
                JOIN {IPPort._meta.db_table} port ON ip."_id" = port.address_id
                LEFT JOIN {Finding._meta.db_table} f on (
                    f.address_id = ip._id and f.finding_type_id = 'KAT-OPEN-COMMON-PORT'
                )
            where f._id is null and (
                (port.protocol = 'TCP' and port.port in ({", ".join(str(x) for x in ALL_COMMON_TCP)}))
                or
                (port.protocol = 'UDP' and port.port in ({", ".join(str(x) for x in COMMON_UDP)}))
            );
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {IPAddress._meta.db_table} ip ON ip._id = f.address_id
                    LEFT JOIN {IPPort._meta.db_table} port ON (
                        port.address_id = ip._id AND
                        (
                            (port.protocol = 'TCP' AND port.port IN ({", ".join(str(x) for x in ALL_COMMON_TCP)}))
                            OR
                            (port.protocol = 'UDP' AND port.port IN ({", ".join(str(x) for x in COMMON_UDP)}))
                        )
                    )
                    WHERE f.finding_type_id = 'KAT-OPEN-COMMON-PORT' and port._id IS NULL
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-OPEN-COMMON-PORT",
        },
        "missing_caa": {
            "name": "missing_caa",
            "description": "Checks if a hostname has a CAA record",
            "object_type": "hostname",
            "requires": ["dns"],
            "query": f"""
            SELECT distinct h._id, h.name, h.network_id, h.root, h.declared, h.scan_level
            FROM {Hostname._meta.db_table} h
                 LEFT JOIN {DNSCAARecord._meta.db_table} dns ON dns.hostname_id = h._id
                 LEFT JOIN {Finding._meta.db_table} f on (f.hostname_id = h._id and f.finding_type_id = 'KAT-NO-CAA')
            where f._id is null and dns._id is null;
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {Hostname._meta.db_table} h ON h._id = f.hostname_id
                    INNER JOIN {DNSCAARecord._meta.db_table} dns ON dns.hostname_id = h._id
                    WHERE f.finding_type_id = 'KAT-NO-CAA'
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-NO-CAA",
        },
        "missing_dmarc": {
            "name": "missing_dmarc",
            "description": "Checks if mail servers have DMARC records",
            "object_type": "hostname",
            "requires": ["dns"],
            "query": f"""
                SELECT h._id, h.name, h.network_id, h.root, h.declared, h.scan_level
                FROM (
                     select host._id, host.name, host.network_id, host.root, host.declared, host.scan_level
                        from {Hostname._meta.db_table} host
                        LEFT JOIN {Finding._meta.db_table} f on (
                            f.hostname_id = host._id and f.finding_type_id = 'KAT-NO-DMARC'
                        ) where f._id is null
                 ) h
                     LEFT JOIN {Hostname._meta.db_table} root_h ON
                (root_h.network_id = h.network_id AND root_h.root = true
                    AND h.name LIKE '%%.' || root_h.name)
                     LEFT JOIN {DNSTXTRecord._meta.db_table} direct_dmarc ON
                (
                    direct_dmarc.hostname_id = h._id
                        AND direct_dmarc.prefix = '_dmarc'
                        AND direct_dmarc.value LIKE_REGEX 'v=dmarc1.' FLAG 'i'
                )
                LEFT JOIN {DNSTXTRecord._meta.db_table} root_dmarc ON
                (
                    root_dmarc.hostname_id = root_h._id
                        AND root_dmarc.prefix = '_dmarc'
                        AND root_dmarc.value LIKE_REGEX 'v=dmarc1.' FLAG 'i'
                )
                WHERE direct_dmarc._id is null and root_dmarc._id is null;
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                SELECT f._id
                FROM {Finding._meta.db_table} f
                INNER JOIN {Hostname._meta.db_table} h ON h._id = f.hostname_id
                LEFT JOIN {Hostname._meta.db_table} root_h ON (
                    root_h.network_id = h.network_id
                    AND root_h.root = true
                    AND h.name LIKE '%%.' || root_h.name
                )
                LEFT JOIN {DNSTXTRecord._meta.db_table} direct_dmarc ON (
                    direct_dmarc.hostname_id = h._id
                    AND direct_dmarc.prefix = '_dmarc'
                    AND direct_dmarc.value LIKE_REGEX 'v=dmarc1.*' FLAG 'i'
                )
                LEFT JOIN {DNSTXTRecord._meta.db_table} root_dmarc ON (
                    root_dmarc.hostname_id = root_h._id
                    AND root_dmarc.prefix = '_dmarc'
                    AND root_dmarc.value LIKE_REGEX 'v=dmarc1.*' FLAG 'i'
                )
                WHERE f.finding_type_id = 'KAT-NO-DMARC' and COALESCE(direct_dmarc._id, root_dmarc._id) IS NOT NULL
            );
            """,  # noqa: S608
            "finding_type_code": "KAT-NO-DMARC",
        },
        "domain_owner_verification": {
            "name": "domain_owner_verification",
            "description": "Checks if the hostname has pending ownership",
            "object_type": "hostname",
            "query": f"""
                 SELECT distinct h._id, h.name, h.network_id, h.root, h.declared, h.scan_level
                 FROM {Hostname._meta.db_table} h
                  JOIN {DNSNSRecord._meta.db_table} hns ON h."_id" = hns."hostname_id"
                  JOIN {Hostname._meta.db_table} nsh ON hns.name_server_id = nsh._id
                  LEFT JOIN {Finding._meta.db_table} f on (
                    f.hostname_id = h._id and f.finding_type_id = 'KAT-DOMAIN-OWNERSHIP-PENDING'
                 )
                 where f._id is null and nsh.name in ({", ".join(f"'{x}'" for x in INDICATORS)})
            """,  # noqa: S608
            "inverse_query": f"""
                DELETE FROM {Finding._meta.db_table}
                WHERE _id IN (
                    SELECT f._id
                    FROM {Finding._meta.db_table} f
                    INNER JOIN {Hostname._meta.db_table} h ON h._id = f.hostname_id
                    LEFT JOIN {DNSNSRecord._meta.db_table} hns ON h."_id" = hns."hostname_id"
                    LEFT JOIN {Hostname._meta.db_table} nsh ON (
                        hns.name_server_id = nsh._id AND
                        nsh.name IN ({", ".join(f"'{x}'" for x in INDICATORS)})
                    )
                    WHERE nsh._id IS NULL
                    AND f.finding_type_id = 'KAT-DOMAIN-OWNERSHIP-PENDING'
                );
            """,  # noqa: S608
            "finding_type_code": "KAT-DOMAIN-OWNERSHIP-PENDING",
        },
    }
    for software in ["mysql", "mongodb", "openssh", "rdp", "pgsql", "telnet", "db2"]:
        rules[f"{software}_detection"] = {
            "name": f"{software}_detection",
            "description": f"Checks if {software} is running on the IPAddress.",
            "object_type": "ipaddress",
            "query": f"""
                SELECT distinct ip._id, ip.address, ip.declared, ip.network_id, ip.scan_level
                FROM {IPAddress._meta.db_table} ip
                    JOIN {IPPort._meta.db_table} port ON ip."_id" = port.address_id
                    JOIN {Software.ports.through._meta.db_table} software_port ON software_port.ipport_id = port._id
                    JOIN {Software._meta.db_table} software ON software_port.software_id = software._id
                    LEFT JOIN {Finding._meta.db_table} f on (
                        f.address_id = ip._id and f.finding_type_id = 'KAT-EXPOSED-SOFTWARE'
                    )
                where f._id is null and lower(software.name) like '%%{software}%%';
            """,  # noqa: S608
            "inverse_query": f"""
            DELETE FROM {Finding._meta.db_table}
            WHERE _id IN (
                SELECT f._id
                FROM {Finding._meta.db_table} f
                INNER JOIN {IPAddress._meta.db_table} ip ON ip._id = f.address_id
                LEFT JOIN {IPPort._meta.db_table} port ON ip."_id" = port.address_id
                LEFT JOIN {Software.ports.through._meta.db_table} software_port ON software_port.ipport_id = port._id
                LEFT JOIN {Software._meta.db_table} software ON (
                    software_port.software_id = software._id AND lower(software.name) like '%%{software}%%'
                )
                WHERE software._id is NULL
                AND f.finding_type_id = 'KAT-EXPOSED-SOFTWARE'
            );""",  # noqa: S608
            "finding_type_code": "KAT-EXPOSED-SOFTWARE",
        }

    return rules


def run_rules(rules: Sequence[BusinessRule] | QuerySet[BusinessRule], dry_run: bool = False) -> None:
    logger.info("Starting business rule recalculation...")

    total_findings = 0

    for rule in rules:
        logger.debug("Processing rule: %s", rule.name)
        logger.debug("Query: %s", rule.query)
        logger.debug("Inverse Query: %s", rule.inverse_query)

        try:
            if rule.inverse_query:
                start = time.time()
                try:
                    with connections["xtdb"].cursor() as cursor:
                        cursor.execute(rule.inverse_query)
                except DatabaseError as e:
                    logger.error("Failed to run inverse query: %s", str(e))

                logger.debug("Inverse query executed in %s seconds", time.time() - start)

            if rule.finding_type_code and rule.query:
                # Get the model class
                model_class = rule.object_type.model_class()
                if not model_class:
                    logger.error("Unknown object type: %s", rule.object_type)
                    continue

                finding_type, created = FindingType.objects.get_or_create(code=rule.finding_type_code)
                queryset = model_class.objects.all()

                if model_class == Hostname and "nameservers_with_ipv6_count" in rule.query:
                    queryset = queryset.annotate(
                        nameservers_with_ipv6_count=Count(
                            Case(
                                When(
                                    dnsnsrecord__name_server__dnsaaaarecord__isnull=False,
                                    then=F("dnsnsrecord__name_server_id"),
                                ),
                                default=None,
                            ),
                            distinct=True,
                        )
                    )
                    schema = HostnameQLSchema
                else:
                    schema = NoOrgQLSchema

                # Apply the query
                start = time.time()
                try:
                    matching_objects = apply_search(queryset, rule.query, schema)
                    match_count = matching_objects.count()
                except DjangoQLError:
                    matching_objects = queryset.raw(rule.query)
                    match_count = len(matching_objects)

                logger.debug("Query executed in %s seconds", time.time() - start)
                logger.debug("Matching objects: %s", match_count)

                findings = []

                matching_objects_with_required = set()
                tasks = Task.objects.filter(type="plugin")

                if rule.requires.exists():
                    for obj in matching_objects:
                        valid = True
                        for plugin in rule.requires.all():
                            if not tasks.filter(
                                data__plugin_id=plugin.plugin_id, data__input_data__has_any_keys=[str(obj)]
                            ).exists():
                                valid = False

                        if valid:
                            matching_objects_with_required.add(obj)
                else:
                    matching_objects_with_required = matching_objects

                for obj in matching_objects_with_required:
                    # Determine which field to set based on the model class
                    finding_kwargs = {"finding_type": finding_type}
                    if model_class == Hostname:
                        finding_kwargs["hostname_id"] = obj.pk
                    elif model_class == IPAddress:
                        finding_kwargs["address_id"] = obj.pk

                    findings.append(Finding(**finding_kwargs))

                total_findings += len(findings)

                if dry_run:
                    logger.warning("[DRY RUN] Skipping finding creation")
                    continue

                bulk_insert(findings)

                logger.debug("Created %s new findings", len(findings))
        except Exception:
            logger.exception("Error processing business rule %s", rule.name)

    if dry_run:
        logger.warning("[DRY RUN] Would have created findings for %s objects", total_findings)
    else:
        logger.info("Completed business rule recalculation, created %s new findings", total_findings)
