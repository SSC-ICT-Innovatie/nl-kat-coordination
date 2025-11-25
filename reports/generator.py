from datetime import datetime
from typing import Any

import structlog
import weasyprint
from django.db.models import CharField, Count, F, QuerySet, Value
from django.template.loader import render_to_string
from django_weasyprint.utils import django_url_fetcher

from files.models import File, ReportContent
from objects.models import DNSNSRecord, Finding, FindingType, Hostname, IPAddress, IPPort, Network
from openkat.models import Organization, User
from reports.models import Report
from tasks.models import ObjectSet

logger = structlog.get_logger(__name__)


class ReportPDFGenerator:
    def __init__(
        self,
        name: str,
        description: str = "",
        organizations: list[Organization] | QuerySet[Organization] | None = None,
        finding_types: list[str] | None = None,
        object_set: ObjectSet | None = None,
        user: User | None = None,
    ):
        self.name = name
        self.description = description
        self.organizations = organizations
        self.finding_types = finding_types
        self.object_set = object_set
        self.user = user

    def generate_pdf_report(self) -> Report:
        logger.info("Starting PDF report generation", report_name=self.name)

        metrics = collect_all_metrics(
            organizations=self.organizations, finding_types=self.finding_types, object_set=self.object_set
        )

        context = {
            "report_name": self.name,
            "description": self.description,
            "generated_at": datetime.now(),
            "organizations": ([org.name for org in self.organizations] if self.organizations else []),
            "finding_types": self.finding_types or [],
            "object_set_id": self.object_set.id if self.object_set else None,
            "metrics": metrics,
            "is_pdf": True,  # Flag to indicate PDF generation mode
        }

        html_content = render_to_string(
            "reports/report_html.html", context | {"base_template": "layouts/pdf_base.html"}
        )
        pdf_bytes = self._html_to_pdf(html_content)
        file_obj = File.objects.create(file=ReportContent(pdf_bytes, name=self.name.replace(" ", "_")), type="pdf")

        if self.organizations:
            file_obj.organizations.set(self.organizations)

        # Prepare report data for storage
        report_data = {
            "report_name": self.name,
            "description": self.description,
            "generated_at": datetime.now().isoformat(),
            "organizations": ([org.name for org in self.organizations] if self.organizations else []),
            "finding_types": self.finding_types or [],
            "object_set_id": self.object_set.id if self.object_set else None,
            "metrics": metrics,
        }

        report = Report.objects.create(
            file=file_obj, name=self.name, description=self.description, object_set=self.object_set, data=report_data
        )

        # Set finding types and organizations
        if self.finding_types:
            report.finding_types = self.finding_types

        if self.organizations:
            report.organizations.set(self.organizations)

        report.save()

        logger.info("PDF report generated successfully", report_id=report.id, file_id=file_obj.id)
        return report

    def _html_to_pdf(self, html_content: str) -> bytes:
        try:
            # Create PDF document
            html = weasyprint.HTML(string=html_content, url_fetcher=django_url_fetcher, base_url="file://")
            pdf = html.write_pdf()
            return pdf
        except Exception as e:
            logger.exception("Failed to generate PDF", error=str(e))
            raise


def collect_all_metrics(
    organizations: list[Organization] | QuerySet[Organization] | None = None,
    finding_types: list[str] | None = None,
    object_set: ObjectSet | None = None,
) -> dict[str, Any]:
    logger.info("Starting report metrics collection")

    metrics = {
        "findings": collect_findings_metrics(organizations, finding_types, object_set),
        "dns": collect_dns_metrics(organizations, object_set),
        "ports": collect_ports_metrics(organizations, object_set),
        "ipv6": collect_ipv6_metrics(organizations, object_set),
        "general": collect_general_metrics(organizations, object_set),
    }

    logger.info("Completed report metrics collection")
    return metrics


def _get_base_finding_query(
    finding_types: list[str] | None = None, organizations: list[Organization] | QuerySet[Organization] | None = None
) -> QuerySet:
    query = Finding.objects.select_related("finding_type").all()

    if finding_types:
        query = query.filter(finding_type__code__in=finding_types)
    if organizations:
        query = query.filter(organizations__pk__in=[org.pk for org in organizations])

    return query


def collect_findings_metrics(
    organizations: list[Organization] | QuerySet[Organization] | None = None,
    finding_types: list[str] | None = None,
    object_set: ObjectSet | None = None,
) -> dict[str, Any]:
    findings = _get_base_finding_query(finding_types, organizations)

    findings_by_type = (
        findings.values("finding_type__code", "finding_type__name", "finding_type__score")
        .annotate(count=Count("id"))
        .order_by("-finding_type__score", "-count")
    )

    hostname_offenders = (
        findings.filter(hostname__isnull=False)
        .values("hostname_id", "hostname__name")
        .annotate(
            finding_count=Count("id"),
            object_id=F("hostname_id"),
            object_type=Value("hostname", output_field=CharField()),
            object_name=F("hostname__name"),
        )
        .order_by("-finding_count")[:10]
    )

    address_offenders = (
        findings.filter(address__isnull=False)
        .values("address_id", "address__address")
        .annotate(
            finding_count=Count("id"),
            object_id=F("address_id"),
            object_type=Value("ipaddress", output_field=CharField()),
            object_name=F("address__address"),
        )
        .order_by("-finding_count")[:10]
    )

    offenders = sorted(
        list(hostname_offenders) + list(address_offenders), key=lambda x: x["finding_count"], reverse=True
    )[:10]

    finding_types_details = {}
    for ft in FindingType.objects.filter(code__in=[f["finding_type__code"] for f in findings_by_type]):
        finding_types_details[ft.code] = {
            "name": ft.name,
            "description": ft.description,
            "recommendation": ft.recommendation,
            "score": ft.score,
            "risk": ft.risk,
        }

    findings_stats = []
    total_assets = _count_total_assets(organizations, object_set)

    for finding_data in findings_by_type:
        ft_code = finding_data["finding_type__code"]
        count = finding_data["count"]

        # Count unique assets affected by this finding type (count hostnames and addresses separately)
        affected_hostnames = (
            findings.filter(finding_type__code=ft_code, hostname__isnull=False).values("hostname_id").distinct().count()
        )
        affected_addresses = (
            findings.filter(finding_type__code=ft_code, address__isnull=False).values("address_id").distinct().count()
        )
        affected_assets = affected_hostnames + affected_addresses
        findings_stats.append(
            {
                "code": ft_code,
                "name": finding_data["finding_type__name"],
                "score": finding_data["finding_type__score"],
                "count": count,
                "affected_assets": affected_assets,
                "affected_percentage": ((affected_assets / total_assets * 100) if total_assets > 0 else 0),
                "details": finding_types_details.get(ft_code, {}),
            }
        )

    return {
        "total_findings": findings.count(),
        "by_type": findings_stats,
        "biggest_offenders": list(offenders),
        "total_assets_scanned": total_assets,
    }


def collect_dns_metrics(
    organizations: list[Organization] | QuerySet[Organization] | None = None, object_set: ObjectSet | None = None
) -> dict[str, Any]:
    dns_query = Hostname.objects.all()
    ns_query = DNSNSRecord.objects.all()

    if organizations:
        dns_query = dns_query.filter(organizations__pk__in=[org.pk for org in organizations])
        ns_query = ns_query.filter(hostname__organizations__pk__in=[org.pk for org in organizations])

    root_domains = dns_query.filter(root=True).count()
    name_servers = ns_query.values("name_server_id").distinct().count()

    return {"total_hostnames": dns_query.count(), "root_domains": root_domains, "name_servers": name_servers}


def collect_ports_metrics(
    organizations: list[Organization] | QuerySet[Organization] | None = None, object_set: ObjectSet | None = None
) -> dict[str, Any]:
    port_query = IPPort.objects.all()

    if organizations:
        port_query = port_query.filter(address__organizations__pk__in=[org.pk for org in organizations])

    total_open_ports = port_query.count()
    ips_with_open_ports = port_query.values("address_id").distinct().count()
    port_distribution = port_query.values("port", "protocol").annotate(count=Count("id")).order_by("-count")[:20]
    by_protocol = port_query.values("protocol").annotate(count=Count("id")).order_by("-count")

    return {
        "total_open_ports": total_open_ports,
        "unique_ips_with_ports": ips_with_open_ports,
        "top_ports": list(port_distribution),
        "by_protocol": list(by_protocol),
    }


def collect_ipv6_metrics(
    organizations: list[Organization] | QuerySet[Organization] | None = None, object_set: ObjectSet | None = None
) -> dict[str, Any]:
    ip_query = IPAddress.objects.all()

    if organizations:
        ip_query = ip_query.filter(organizations__pk__in=[org.pk for org in organizations])

    ipv6_count = ip_query.filter(address__contains=":").count()
    total_ips = ip_query.count()

    return {
        "ipv6_addresses": ipv6_count,
        "ipv4_addresses": ip_query.filter(address__contains=".").count(),
        "total_ip_addresses": total_ips,
        "ipv6_percentage": (ipv6_count / total_ips * 100) if total_ips > 0 else 0,
    }


def collect_general_metrics(
    organizations: list[Organization] | QuerySet[Organization] | None = None, object_set: ObjectSet | None = None
) -> dict[str, Any]:
    total_networks = Network.objects.all()
    total_hostnames = Hostname.objects.all()
    total_ips = IPAddress.objects.all()

    if organizations:
        org_count = len(organizations) if isinstance(organizations, list) else organizations.count()
        total_networks = total_networks.filter(organizations__pk__in=[org.pk for org in organizations])
        total_hostnames = total_hostnames.filter(organizations__pk__in=[org.pk for org in organizations])
        total_ips = total_ips.filter(organizations__pk__in=[org.pk for org in organizations])
    else:
        org_count = 0

    return {
        "total_networks": total_networks.count(),
        "total_hostnames": total_hostnames.count(),
        "total_ip_addresses": total_ips.count(),
        "organizations_count": org_count,
    }


def _count_total_assets(
    organizations: list[Organization] | QuerySet[Organization] | None = None, object_set: ObjectSet | None = None
) -> int:
    total_hostnames = Hostname.objects.all()
    total_ips = IPAddress.objects.all()

    if organizations:
        total_hostnames = total_hostnames.filter(organizations__pk__in=[org.pk for org in organizations])
        total_ips = total_ips.filter(organizations__pk__in=[org.pk for org in organizations])

    return total_hostnames.count() + total_ips.count()
