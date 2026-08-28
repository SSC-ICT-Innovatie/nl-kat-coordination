import binascii
import json
import logging
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv6Address
from os import urandom
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
import structlog
from crisis_room.models import Dashboard, DashboardItem
from crisis_room.views import DashboardItemView, DashboardService
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.translation import activate, deactivate
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.middleware import OTPMiddleware
from httpx import Response
from katalogus.client import Boefje, parse_plugin
from reports.report_types.findings_report.report import FindingsReport
from tools.enums import SCAN_LEVEL
from tools.models import GROUP_ADMIN, GROUP_CLIENT, GROUP_REDTEAM, Indemnification, Organization, OrganizationMember

from octopoes.config.settings import (
    DEFAULT_LIMIT,
    DEFAULT_OFFSET,
    DEFAULT_SCAN_LEVEL_FILTER,
    DEFAULT_SCAN_PROFILE_TYPE_FILTER,
)
from octopoes.models import OOI, DeclaredScanProfile, EmptyScanProfile, Reference, ScanLevel, ScanProfileType
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import CVEFindingType, Finding, KATFindingType, RiskLevelSeverity
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, Protocol
from octopoes.models.ooi.reports import AssetReport, HydratedReport, Report, ReportData, ReportRecipe
from octopoes.models.ooi.service import IPService, Service, TLSCipher
from octopoes.models.ooi.software import Software
from octopoes.models.ooi.web import URL, SecurityTXT, Website
from octopoes.models.origin import Origin, OriginType
from octopoes.models.pagination import Paginated
from octopoes.models.transaction import TransactionRecord
from octopoes.models.tree import ReferenceTree
from octopoes.models.types import OOIType
from rocky.health import ServiceHealth
from rocky.scheduler import PaginatedTasksResponse, ReportTask, ScheduleResponse, Task, TaskStatus

LANG_LIST = [code for code, _ in settings.LANGUAGES]

# Quiet faker locale messages down in tests.
logging.getLogger("faker").setLevel(logging.INFO)


# Copied from https://www.structlog.org/en/stable/testing.html
@pytest.fixture
def log_output():
    return structlog.testing.LogCapture()


@pytest.fixture(autouse=True)
def fixture_configure_structlog(log_output):
    structlog.configure(processors=[log_output])


@pytest.fixture
def valid_time():
    return datetime.now(timezone.utc)


@pytest.fixture(params=LANG_LIST)
def current_language(request):
    return request.param


@pytest.fixture
def language(current_language):
    activate(current_language)
    yield current_language
    deactivate()


def create_user(django_user_model, email, password, name, device_name, superuser=False):
    user = django_user_model.objects.create_user(email=email, password=password)
    user.full_name = name
    user.is_verified = lambda: True
    user.is_superuser = superuser
    user.save()
    device = user.staticdevice_set.create(name=device_name)
    device.token_set.create(token=binascii.hexlify(urandom(8)).decode())
    return user


def create_organization(name, organization_code):
    katalogus_client = "katalogus.client.KATalogusClient"
    octopoes_node = "rocky.signals.OctopoesAPIConnector"
    scheduler_client = "crisis_room.management.commands.dashboards.scheduler_client"
    bytes_client = "crisis_room.management.commands.dashboards.get_bytes_client"

    with patch(katalogus_client), patch(octopoes_node), patch(scheduler_client), patch(bytes_client):
        return Organization.objects.create(name=name, code=organization_code)


def create_member(user, organization):
    Indemnification.objects.create(user=user, organization=organization)

    return OrganizationMember.objects.create(
        user=user,
        organization=organization,
        status=OrganizationMember.STATUSES.ACTIVE,
        blocked=False,
        trusted_clearance_level=4,
        acknowledged_clearance_level=4,
        onboarded=False,
    )


def add_admin_group_permissions(member):
    group = Group.objects.get(name=GROUP_ADMIN)
    member.groups.add(group)
    admin_permissions = [
        Permission.objects.get(codename="view_organization").id,
        Permission.objects.get(codename="view_organizationmember").id,
        Permission.objects.get(codename="add_organizationmember").id,
        Permission.objects.get(codename="change_organization").id,
        Permission.objects.get(codename="change_organizationmember").id,
        Permission.objects.get(codename="can_delete_oois").id,
        Permission.objects.get(codename="add_indemnification").id,
        Permission.objects.get(codename="can_scan_organization").id,
        Permission.objects.get(codename="add_dashboard").id,
        Permission.objects.get(codename="change_dashboard").id,
        Permission.objects.get(codename="delete_dashboard").id,
        Permission.objects.get(codename="add_dashboarditem").id,
        Permission.objects.get(codename="change_dashboarditem").id,
        Permission.objects.get(codename="delete_dashboarditem").id,
        Permission.objects.get(codename="change_dashboarditem_position").id,
    ]
    group.permissions.set(admin_permissions)


def add_redteam_group_permissions(member):
    group = Group.objects.get(name=GROUP_REDTEAM)
    member.groups.add(group)

    redteam_permissions = [
        Permission.objects.get(codename="can_scan_organization").id,
        Permission.objects.get(codename="can_enable_disable_boefje").id,
        Permission.objects.get(codename="can_set_clearance_level").id,
        Permission.objects.get(codename="can_delete_oois").id,
        Permission.objects.get(codename="can_mute_findings").id,
        Permission.objects.get(codename="can_view_katalogus_settings").id,
        Permission.objects.get(codename="can_set_katalogus_settings").id,
        Permission.objects.get(codename="add_dashboard").id,
        Permission.objects.get(codename="change_dashboard").id,
        Permission.objects.get(codename="delete_dashboard").id,
        Permission.objects.get(codename="add_dashboarditem").id,
        Permission.objects.get(codename="change_dashboarditem").id,
        Permission.objects.get(codename="delete_dashboarditem").id,
        Permission.objects.get(codename="change_dashboarditem_position").id,
    ]
    group.permissions.set(redteam_permissions)


def add_client_group_permissions(member):
    group = Group.objects.get(name=GROUP_CLIENT)
    member.groups.add(group)
    client_permissions = [Permission.objects.get(codename="can_scan_organization").id]
    group.permissions.set(client_permissions)
    member.user.user_permissions.set(client_permissions)


@pytest.fixture(autouse=True)
def seed_groups(db):
    Group.objects.get_or_create(name=GROUP_CLIENT)
    Group.objects.get_or_create(name=GROUP_REDTEAM)
    Group.objects.get_or_create(name=GROUP_ADMIN)


@pytest.fixture
def organization():
    return create_organization("Test Organization", "test")


@pytest.fixture
def organization_b():
    return create_organization("OrganizationB", "org_b")


@pytest.fixture
def superuser(django_user_model):
    return create_user(
        django_user_model, "superuser@openkat.nl", "SuperSuper123!!", "Superuser name", "default", superuser=True
    )


@pytest.fixture
def superuser_b(django_user_model):
    return create_user(
        django_user_model, "superuserB@openkat.nl", "SuperBSuperB123!!", "Superuser B name", "default_b", superuser=True
    )


@pytest.fixture
def superuser_member(superuser, organization):
    return create_member(superuser, organization)


@pytest.fixture
def superuser_member_b(superuser_b, organization_b):
    return create_member(superuser_b, organization_b)


@pytest.fixture
def adminuser(django_user_model):
    return create_user(django_user_model, "admin@openkat.nl", "AdminAdmin123!!", "Admin name", "default_admin")


@pytest.fixture
def adminuser_b(django_user_model):
    return create_user(django_user_model, "adminB@openkat.nl", "AdminBAdminB123!!", "Admin B name", "default_admin_b")


@pytest.fixture
def admin_member(adminuser, organization):
    member = create_member(adminuser, organization)
    adminuser.user_permissions.add(Permission.objects.get(codename="view_organization"))
    add_admin_group_permissions(member)
    return member


@pytest.fixture
def admin_member_b(adminuser_b, organization_b):
    member = create_member(adminuser_b, organization_b)
    adminuser_b.user_permissions.add(Permission.objects.get(codename="view_organization"))
    add_admin_group_permissions(member)
    return member


@pytest.fixture
def redteamuser(django_user_model):
    return create_user(
        django_user_model, "redteamer@openkat.nl", "RedteamRedteam123!!", "Redteam name", "default_redteam"
    )


@pytest.fixture
def redteam_member(redteamuser, organization):
    member = create_member(redteamuser, organization)
    add_redteam_group_permissions(member)
    return member


@pytest.fixture
def clientuser(django_user_model):
    return create_user(django_user_model, "client@openkat.nl", "ClientClient123!!", "Client name", "default_client")


@pytest.fixture
def clientuser_b(django_user_model):
    return create_user(
        django_user_model, "clientB@openkat.nl", "ClientBClientB123!!", "Client B name", "default_client_b"
    )


@pytest.fixture
def client_member(clientuser, organization):
    member = create_member(clientuser, organization)
    add_client_group_permissions(member)
    return member


@pytest.fixture
def client_member_b(clientuser_b, organization_b):
    member = create_member(clientuser_b, organization_b)
    add_client_group_permissions(member)
    return member


@pytest.fixture
def client_user_two_organizations(clientuser, organization, organization_b):
    member = create_member(clientuser, organization)
    add_client_group_permissions(member)
    member = create_member(clientuser, organization_b)
    add_client_group_permissions(member)
    return clientuser


@pytest.fixture
def new_member(django_user_model, organization):
    user = create_user(django_user_model, "cl1@openkat.nl", "TestTest123!!", "New user", "default_new_user")
    member = create_member(user, organization)
    member.status = OrganizationMember.STATUSES.NEW
    member.save()
    return member


@pytest.fixture
def active_member(django_user_model, organization):
    user = create_user(django_user_model, "cl2@openkat.nl", "TestTest123!!", "Active user", "default_active_user")
    member = create_member(user, organization)
    member.status = OrganizationMember.STATUSES.ACTIVE
    member.save()
    return member


@pytest.fixture
def blocked_member(django_user_model, organization):
    user = create_user(django_user_model, "cl3@openkat.nl", "TestTest123!!", "Blocked user", "default_blocked_user")
    member = create_member(user, organization)
    member.status = OrganizationMember.STATUSES.ACTIVE
    member.blocked = True
    member.save()
    return member


@pytest.fixture
def mock_models_katalogus(mocker):
    return mocker.patch("katalogus.client.get_katalogus_client")


@pytest.fixture
def mock_bytes_client(mocker):
    return mocker.patch("rocky.bytes_client.BytesClient")


@pytest.fixture
def mock_models_octopoes(mocker):
    return mocker.patch("rocky.signals.OctopoesAPIConnector")


@pytest.fixture
def mock_organization_view_octopoes(mocker):
    return mocker.patch("account.mixins.OctopoesAPIConnector")


@pytest.fixture
def mock_crisis_room_octopoes(mocker):
    return mocker.patch("crisis_room.views.OctopoesAPIConnector")


@pytest.fixture
def task() -> Task:
    return Task.model_validate(
        {
            "id": "1b20f85f-63d5-4baa-be9e-f3f19d6e3fae",
            "hash": "19ed51514b37d42f79c5e95469956b05",
            "scheduler_id": "boefje-test",
            "schedule_id": None,
            "organisation": "test",
            "type": "boefje",
            "priority": 1,
            "data": {
                "id": "1b20f85f63d54baabe9ef3f19d6e3fae",
                "boefje": {
                    "id": "test-boefje",
                    "name": "TestBoefje",
                    "description": "Fetch the DNS record(s) of a hostname",
                    "version": None,
                    "scan_level": 1,
                    "consumes": ["Hostname"],
                    "produces": [
                        "DNSNSRecord",
                        "DNSARecord",
                        "DNSCNAMERecord",
                        "DNSMXRecord",
                        "DNSZone",
                        "Hostname",
                        "DNSAAAARecord",
                        "IPAddressV4",
                        "DNSSOARecord",
                        "DNSTXTRecord",
                        "IPAddressV6",
                        "Network",
                        "NXDOMAIN",
                    ],
                },
                "input_ooi": "Hostname|internet|mispo.es",
                "organization": "test",
            },
            "status": "completed",
            "created_at": "2022-08-09 11:53:41.378292",
            "modified_at": "2022-08-09 11:54:21.002838",
        }
    )


@pytest.fixture
def bytes_raw_metas():
    return [
        {
            "id": "85c01c8c-c0bf-4fe8-bda5-abdf2d03117c",
            "boefje_meta": {
                "id": "6dea9549-c05d-42c9-b55b-8ad54cb9e413",
                "started_at": "2023-11-01T15:02:46.764085+00:00",
                "ended_at": "2023-11-01T15:02:47.276154+00:00",
                "boefje": {"id": "dns-sec", "version": None},
                "input_ooi": "Hostname|internet|mispoes.nl",
                "arguments": {},
                "organization": "test",
                "runnable_hash": "ed871e9731f3d528ea92ca23c8eb18f38ac47e6d89a634b654a073fc2ca5fb50",
                "environment": {},
            },
            "mime_types": [
                {"value": "boefje/dns-sec"},
                {"value": "boefje/dns-sec-c90404f60aeacf9b254abbd250bd3214e3b1a65b5a883dcbc"},
                {"value": "dns-sec"},
            ],
            "secure_hash": "sha512:23e40f3e0c4381b89a296a5708a3c7a2dff369dc272b5cbce584d0fd7e17b1a5ebb1a947"
            "be36ed19e8930116a46be2f4b450353b786696f83c328f197a8ae741",
            "signing_provider_url": None,
            "hash_retrieval_link": "a9b261d1-e981-42db-bd92-ee0c36372678",
        }
    ]


@pytest.fixture
def bytes_get_raw():
    byte_string = ";; Number of trusted keys: 2\\n;; Chasing: mispoes.nl."
    " A\\n\\n\\nDNSSEC Trust tree:\\nantagonist.nl. (A)\\n|---mispoes.nl. (DNSKEY keytag: 47684 alg: 13 flags:"
    " 257)\\n    |---mispoes.nl. (DS keytag: 47684 digest type: 2)\\n        "
    "|---nl. (DNSKEY keytag: 52707 alg: 13 flags: 256)\\n            "
    "|---nl. (DNSKEY keytag: 17153 alg: 13 flags: 257)\\n            "
    "|---nl. (DS keytag: 17153 digest type: 2)\\n                "
    "|---. (DNSKEY keytag: 46780 alg: 8 flags: 256)\\n                    "
    b"|---. (DNSKEY keytag: 20326 alg: 8 flags: 257)\\n;; Chase successful\\n"

    return byte_string.encode()


@pytest.fixture
def lazy_task_list_with_boefje(task) -> MagicMock:
    mock = MagicMock()
    mock.__getitem__.return_value = [task]
    mock.count.return_value = 1
    return mock


@pytest.fixture
def network() -> Network:
    return Network(
        name="testnetwork",
        scan_profile=DeclaredScanProfile(reference=Reference.from_str("Network|testnetwork"), level=ScanLevel.L1),
    )


@pytest.fixture
def url(network) -> URL:
    return URL(
        scan_profile=DeclaredScanProfile(
            scan_profile_type="declared", reference=Reference("URL|testnetwork|http://example.com/"), level=ScanLevel.L1
        ),
        network=network.reference,
        raw="http://example.com",
        web_url=Reference("HostnameHTTPURL|http|testnetwork|example.com|80|/"),
    )


@pytest.fixture
def ipaddressv4(network) -> IPAddressV4:
    return IPAddressV4(network=network.reference, address=IPv4Address("192.0.2.1"))


@pytest.fixture
def ipaddressv6(network) -> IPAddressV6:
    return IPAddressV6(network=network.reference, address=IPv6Address("2001:db8::1"))


@pytest.fixture
def ip_port(ipaddressv4) -> IPPort:
    return IPPort(address=ipaddressv4.reference, port=80, protocol=Protocol.TCP)


@pytest.fixture
def ip_port_443(ipaddressv4) -> IPPort:
    return IPPort(address=ipaddressv4.reference, port=443, protocol=Protocol.TCP)


@pytest.fixture
def hostname(network) -> Hostname:
    return Hostname(name="example.com", network=network.reference)


@pytest.fixture
def website(ip_service: IPService, hostname: Hostname):
    return Website(ip_service=ip_service.reference, hostname=hostname.reference)


@pytest.fixture
def security_txt(website: Website, url: URL):
    return SecurityTXT(website=website.reference, url=url.reference, security_txt="example")


@pytest.fixture
def service() -> Service:
    return Service(name="domain")


@pytest.fixture
def ip_service(ip_port: IPPort, service: Service):
    return IPService(ip_port=ip_port.reference, service=service.reference)


@pytest.fixture
def software() -> Software:
    return Software(name="DICOM")


@pytest.fixture
def cve_finding_type_2023_38408() -> CVEFindingType:
    return CVEFindingType(
        id="CVE-2023-38408",
        description="The PKCS#11 feature in ssh-agent in OpenSSH before 9.3p2 has an insufficiently "
        "trustworthy search path, leading to remote code execution if an agent is forwarded to an "
        "attacker-controlled system. ",
        source="https://cve.circl.lu/cve/CVE-2023-38408",
        risk_score=9.8,
        risk_severity=RiskLevelSeverity.CRITICAL,
    )


@pytest.fixture
def cve_finding_type_2019_8331() -> CVEFindingType:
    return CVEFindingType(
        id="CVE-2019-8331",
        description="In Bootstrap before 3.4.1 and 4.3.x before 4.3.1, XSS is possible in the tooltip or "
        "popover data-template attribute.",
        source="https://cve.circl.lu/cve/CVE-2019-8331",
        risk_score=6.1,
        risk_severity=RiskLevelSeverity.MEDIUM,
    )


@pytest.fixture
def cve_finding_type_2019_2019() -> CVEFindingType:
    return CVEFindingType(
        id="CVE-2019-2019",
        description="In ce_t4t_data_cback of ce_t4t.cc, there is a possible out-of-bound read due to a missing bounds "
        "check. This could lead to local information disclosure with no additional execution privileges "
        "needed. User interaction is needed for exploitation.Product: AndroidVersions: Android-7.0 "
        "Android-7.1.1 Android-7.1.2 Android-8.0 Android-8.1 Android-9Android ID: A-115635871",
        source="https://cve.circl.lu/cve/CVE-2019-2019",
        risk_score=6.5,
        risk_severity=RiskLevelSeverity.MEDIUM,
    )


@pytest.fixture
def cve_finding_2023_38408() -> Finding:
    return Finding(
        finding_type=Reference.from_str("CVEFindingType|CVE-2023-38408"),
        ooi=Reference.from_str(
            "Finding|SoftwareInstance|HostnameHTTPURL|https|internet|mispo.es|443|/|Software|Bootstrap|3.3.7|cpe:/a:getbootstrap:bootstrap|CVE-2023-38408"
        ),
        proof=None,
        description="Vulnerability CVE-2023-38408 detected",
        reproduce=None,
    )


@pytest.fixture
def cve_finding_2019_8331() -> Finding:
    return Finding(
        finding_type=Reference.from_str("CVEFindingType|CVE-2019-8331"),
        ooi=Reference.from_str(
            "Finding|SoftwareInstance|HostnameHTTPURL|https|internet|mispo.es|443|/|Software|Bootstrap|3.3.7|cpe:/a:getbootstrap:bootstrap|CVE-2019-8331"
        ),
        proof=None,
        description="Vulnerability CVE-2019-8331 detected",
        reproduce=None,
    )


@pytest.fixture
def cve_finding_2019_2019() -> Finding:
    return Finding(
        finding_type=Reference.from_str("CVEFindingType|CVE-2019-2019"),
        ooi=Reference.from_str(
            "Finding|SoftwareInstance|HostnameHTTPURL|https|internet|mispo.es|443|/|Software|Bootstrap|3.3.7|cpe:/a:getbootstrap:bootstrap|CVE-2019-2019"
        ),
        proof=None,
        description="Vulnerability CVE-2019-2019 detected",
        reproduce=None,
    )


@pytest.fixture
def cve_finding_type_no_score() -> CVEFindingType:
    return CVEFindingType(
        id="CVE-0000-0001",
        description="CVE Finding without score",
        source="https://cve.circl.lu/cve/CVE-0000-0001",
        risk_severity=RiskLevelSeverity.UNKNOWN,
    )


@pytest.fixture
def cve_finding_no_score() -> Finding:
    return Finding(
        finding_type=Reference.from_str("CVEFindingType|CVE-0000-0001"),
        ooi=Reference.from_str(
            "Finding|SoftwareInstance|HostnameHTTPURL|https|internet|mispo.es|443|/|Software|Bootstrap|3.3.7|cpe:/a:getbootstrap:bootstrap|CVE-0000-0001"
        ),
        proof=None,
        description="Vulnerability CVE-0000-0001 detected",
        reproduce=None,
    )


@pytest.fixture
def finding() -> Finding:
    return Finding(
        finding_type=Reference.from_str("KATFindingType|KAT-0001"),
        ooi=Reference.from_str("Network|testnetwork"),
        proof="proof",
        description="description",
        reproduce="reproduce",
    )


@pytest.fixture
def web_report_finding_types():
    return [
        KATFindingType(id="KAT-NO-CSP"),
        KATFindingType(id="KAT-CSP-VULNERABILITIES"),
        KATFindingType(id="KAT-NO-HTTPS-REDIRECT"),
        KATFindingType(id="KAT-NO-CERTIFICATE"),
        KATFindingType(id="KAT-NO-SECURITY-TXT"),
        KATFindingType(id="KAT-UNCOMMON-OPEN-PORT"),
        KATFindingType(id="KAT-OPEN-SYSADMIN-PORT"),
        KATFindingType(id="KAT-OPEN-DATABASE-PORT"),
        KATFindingType(id="KAT-CERTIFICATE-EXPIRED"),
        KATFindingType(id="KAT-CERTIFICATE-EXPIRING-SOON"),
    ]


@pytest.fixture
def no_rpki_finding_type() -> KATFindingType:
    return KATFindingType(id="KAT-NO-RPKI")


@pytest.fixture
def invalid_rpki_finding_type() -> KATFindingType:
    return KATFindingType(id="KAT-INVALID-RPKI")


@pytest.fixture
def finding_types() -> list[KATFindingType]:
    return [
        KATFindingType(
            id="KAT-0001",
            description="Fake description...",
            recommendation="Fake recommendation...",
            risk_score=9.5,
            risk_severity=RiskLevelSeverity.CRITICAL,
        ),
        KATFindingType(
            id="KAT-0002",
            description="Fake description...",
            recommendation="Fake recommendation...",
            risk_score=9.5,
            risk_severity=RiskLevelSeverity.CRITICAL,
        ),
        KATFindingType(
            id="KAT-0003",
            description="Fake description...",
            recommendation="Fake recommendation...",
            risk_score=3.9,
            risk_severity=RiskLevelSeverity.LOW,
        ),
    ]


@pytest.fixture
def tree_data_no_findings():
    return {
        "root": {
            "reference": "Finding|Network|testnetwork|KAT-0001",
            "children": {"ooi": [{"reference": "Network|testnetwork", "children": {}}]},
        },
        "store": {},
    }


@pytest.fixture
def tree_data_findings():
    return {
        "root": {
            "reference": "Finding|Network|testnetwork|KAT-0001",
            "children": {"ooi": [{"reference": "Network|testnetwork", "children": {}}]},
        },
        "store": {
            "Network|testnetwork": {
                "object_type": "Network",
                "primary_key": "Network|testnetwork",
                "name": "testnetwork",
            },
            "Finding|Network|testnetwork|KAT-0001": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0001",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-0001",
            },
            "Finding|Network|testnetwork|KAT-0002": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0002",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-0002",
            },
            "Finding|Network|testnetwork|KAT-0003": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0003",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-0001",
            },
        },
    }


@pytest.fixture
def tree_data_dns_findings():
    return {
        "root": {
            "reference": "Finding|Network|testnetwork|KAT-0001",
            "children": {"ooi": [{"reference": "Network|testnetwork", "children": {}}]},
        },
        "store": {
            "Finding|Network|testnetwork|KAT-0001": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0001",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-NO-CAA",
            },
            "Finding|Network|testnetwork|KAT-0002": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0002",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-NO-DKIM",
            },
            "Finding|Network|testnetwork|KAT-0003": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0003",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-NO-DMARC",
            },
            "Finding|Network|testnetwork|KAT-0004": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0004",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-NO-DNSSEC",
            },
            "Finding|Network|testnetwork|KAT-0005": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0005",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-NO-SPF",
            },
            "Finding|Network|testnetwork|KAT-0006": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0006",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-INVALID-SPF",
            },
            "Finding|Network|testnetwork|KAT-0007": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0007",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-NAMESERVER-NO-IPV6",
            },
            "Finding|Network|testnetwork|KAT-0008": {
                "object_type": "Finding",
                "primary_key": "Finding|Network|testnetwork|KAT-0008",
                "ooi": "Network|testnetwork",
                "finding_type": "KATFindingType|KAT-NAMESERVER-NO-TWO-IPV6",
            },
            "DNSSOARecord|Network|testnetwork|KAT-0009": {
                "object_type": "DNSSOARecord",
                "primary_key": "DNSSOARecord|Network|testnetwork|KAT-0009",
                "hostname": "Hostname|internet|example.com",
                "dns_record_type": "SOA",
                "value": "fake value",
                "ttl": 3600,
                "soa_hostname": "Hostname|internet|example.com",
            },
            "DNSARecord|Network|testnetwork|KAT-00010": {
                "object_type": "DNSARecord",
                "primary_key": "DNSARecord|Network|testnetwork|KAT-00010",
                "hostname": "Hostname|internet|example.com",
                "dns_record_type": "A",
                "value": "fake value",
                "address": "IPAddressV4|internet|127.0.0.1",
            },
        },
    }


@pytest.fixture
def finding_type_kat_invalid_spf() -> KATFindingType:
    return KATFindingType(
        id="KAT-INVALID-SPF",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=6.0,
        risk_severity=RiskLevelSeverity.MEDIUM,
    )


@pytest.fixture
def finding_type_kat_nameserver_no_ipv6() -> KATFindingType:
    return KATFindingType(
        id="KAT-NAMESERVER-NO-IPV6",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=9.5,
        risk_severity=RiskLevelSeverity.CRITICAL,
    )


@pytest.fixture
def finding_type_kat_no_two_ipv6() -> KATFindingType:
    return KATFindingType(
        id="KAT-NAMESERVER-NO-TWO-IPV6",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=1.0,
        risk_severity=RiskLevelSeverity.LOW,
    )


@pytest.fixture
def cipher_finding_types() -> list[KATFindingType]:
    return [
        KATFindingType(
            id="KAT-RECOMMENDATION-BAD-CIPHER",
            description="Fake description...",
            recommendation="Fake recommendation...",
            risk_score=3.0,
            risk_severity=RiskLevelSeverity.RECOMMENDATION,
        ),
        KATFindingType(
            id="KAT-CRITICAL-BAD-CIPHER",
            description="Fake description...",
            recommendation="Fake recommendation...",
            risk_score=10.0,
            risk_severity=RiskLevelSeverity.CRITICAL,
        ),
    ]


@pytest.fixture
def cipher_finding_type() -> KATFindingType:
    return KATFindingType(
        id="KAT-MEDIUM-BAD-CIPHER",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=6.0,
        risk_severity=RiskLevelSeverity.MEDIUM,
    )


@pytest.fixture
def finding_type_kat_no_spf() -> KATFindingType:
    return KATFindingType(
        id="KAT-NO-SPF",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=9.5,
        risk_severity=RiskLevelSeverity.CRITICAL,
    )


@pytest.fixture
def finding_type_kat_no_dmarc() -> KATFindingType:
    return KATFindingType(
        id="KAT-NO-DMARC",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=9.5,
        risk_severity=RiskLevelSeverity.CRITICAL,
    )


@pytest.fixture
def finding_type_kat_no_dkim() -> KATFindingType:
    return KATFindingType(
        id="KAT-NO-DKIM",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=9.5,
        risk_severity=RiskLevelSeverity.CRITICAL,
    )


@pytest.fixture
def finding_type_kat_uncommon_open_port() -> KATFindingType:
    return KATFindingType(
        id="KAT-UNCOMMON-OPEN-PORT",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=9.5,
        risk_severity=RiskLevelSeverity.CRITICAL,
    )


@pytest.fixture
def finding_type_kat_open_sysadmin_port() -> KATFindingType:
    return KATFindingType(
        id="KAT-OPEN-SYSADMIN-PORT",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=8.5,
        risk_severity=RiskLevelSeverity.HIGH,
    )


@pytest.fixture
def finding_type_kat_open_database_port() -> KATFindingType:
    return KATFindingType(
        id="KAT-OPEN-DATABASE-PORT",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_score=6.5,
        risk_severity=RiskLevelSeverity.MEDIUM,
    )


@pytest.fixture
def finding_type_kat_no_dnssec() -> KATFindingType:
    return KATFindingType(
        id="KAT-NO-DNSSEC",
        description="Fake description...",
        recommendation="Fake recommendation...",
        risk_severity=RiskLevelSeverity.PENDING,
    )


@pytest.fixture
def finding_type_kat_invalid_dnssec() -> KATFindingType:
    return KATFindingType(
        id="KAT-INVALID-DNSSEC",
        recommendation="Fake recommendation...",
        risk_score=3.0,
        risk_severity=RiskLevelSeverity.LOW,
    )


@pytest.fixture
def cipher(ip_service: IPService) -> TLSCipher:
    return TLSCipher(
        ip_service=ip_service.reference,
        suites={
            "TLSv1": [
                {
                    "cipher_suite_alias": "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
                    "encryption_algorithm": "AES",
                    "cipher_suite_name": "ECDHE-RSA-AES128-SHA",
                    "bits": 128,
                    "key_size": 256,
                    "key_exchange_algorithm": "ECDH",
                    "cipher_suite_code": "xc013",
                },
                {
                    "cipher_suite_alias": "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
                    "encryption_algorithm": "AES",
                    "cipher_suite_name": "ECDHE-RSA-AES256-SHA",
                    "bits": 256,
                    "key_size": 256,
                    "key_exchange_algorithm": "ECDH",
                    "cipher_suite_code": "xc014",
                },
            ]
        },
    )


@pytest.fixture
def query_data_tls_findings_and_suites(cipher):
    return [
        Finding(
            ooi=cipher.reference,
            description="Fake description with cipher_suite_name ECDHE-RSA-AES128-SHA",
            finding_type=KATFindingType(id="KAT-RECOMMENDATION-BAD-CIPHER").reference,
        ),
        Finding(
            ooi=cipher.reference,
            description="Fake description with cipher_suite_name ECDHE-RSA-AES256-SHA",
            finding_type=KATFindingType(id="KAT-MEDIUM-BAD-CIPHER").reference,
        ),
        Finding(
            ooi=cipher.reference,
            description="Fake description...",
            finding_type=KATFindingType(id="KAT-CRITICAL-BAD-CIPHER").reference,
        ),
    ]


@pytest.fixture
def plugin_details(plugin_schema):
    return parse_plugin(
        {
            "id": "test-boefje",
            "type": "boefje",
            "name": "TestBoefje",
            "created": "2023-05-09T09:37:20.909069+00:00",
            "description": "Meows to the moon",
            "scan_level": 1,
            "consumes": ["Network"],
            "produces": ["Network"],
            "enabled": True,
            "boefje_schema": plugin_schema,
            "oci_image": None,
            "oci_arguments": ["-test", "-arg"],
        }
    )


@pytest.fixture
def plugin_details_with_container(plugin_schema):
    return parse_plugin(
        {
            "id": "test-boefje",
            "type": "boefje",
            "name": "TestBoefje",
            "created": "2023-05-09T09:37:20.909069+00:00",
            "description": "Meows to the moon",
            "scan_level": 1,
            "consumes": ["Network"],
            "produces": ["Network"],
            "enabled": True,
            "boefje_schema": plugin_schema,
            "oci_image": "ghcr.io/test/image:123",
            "oci_arguments": ["-test", "-arg"],
        }
    )


@pytest.fixture
def plugin_schema():
    return {
        "title": "Arguments",
        "type": "object",
        "properties": {
            "TEST_PROPERTY": {
                "title": "TEST_PROPERTY",
                "maxLength": 128,
                "type": "string",
                "description": "Test description",
            },
            "TEST_PROPERTY2": {
                "title": "TEST_PROPERTY2",
                "type": "integer",
                "minimum": 2,
                "maximum": 200,
                "description": "Test description2",
            },
        },
        "required": ["TEST_PROPERTY"],
    }


@pytest.fixture
def plugin_schema_no_required():
    return {
        "title": "Arguments",
        "type": "object",
        "properties": {
            "TEST_PROPERTY": {
                "title": "TEST_PROPERTY",
                "maxLength": 128,
                "type": "string",
                "description": "Test description",
            },
            "TEST_PROPERTY2": {
                "title": "TEST_PROPERTY2",
                "type": "integer",
                "minimum": 2,
                "maximum": 200,
                "description": "Test description2",
            },
        },
    }


recipe = ReportRecipe(
    report_type="concatenated-report",
    recipe_id=uuid.uuid4(),
    report_name_format="test",
    cron_expression="* * * *",
    input_recipe={},
    asset_report_types=[],
)

parent_report = HydratedReport(
    report_recipe=recipe.reference,
    primary_key="Report|e821aaeb-a6bd-427f-b064-e46837911a5d",
    name="Test Parent Report",
    report_type="concatenated-report",
    template="report.html",
    date_generated=datetime(2024, 1, 1, 23, 59, 59, 999999),
    reference_date=datetime(2024, 1, 1, 23, 59, 59, 999999),
    input_oois=[],
    organization_code="test_organization",
    organization_name="Test Organization",
    organization_tags=[],
    data_raw_id="a5ccf97b-d4e9-442d-85bf-84e739b6d3ed",
    observed_at=datetime(2024, 1, 1, 23, 59, 59, 999999),
)


def create_asset_report(
    name,
    report_type,
    template,
    uuid_iterator: Iterator,
    input_ooi="Hostname|internet|example.com",
    organization_code: str = "test",
    organization_name: str = "Test Organization",
) -> AssetReport:
    return AssetReport(
        report_recipe=recipe.reference,
        name=name,
        report_type=report_type,
        template=template,
        date_generated=datetime(2024, 1, 1, 23, 59, 59, 999999),
        reference_date=datetime(2024, 1, 1, 23, 59, 59, 999999),
        input_ooi=input_ooi,
        organization_code=organization_code,
        organization_name=organization_name,
        organization_tags=[],
        data_raw_id=str(next(uuid_iterator)),
        observed_at=datetime(2024, 1, 1, 23, 59, 59, 999999),
    )


def create_report(
    name, report_type, template, asset_reports: list[AssetReport] | None, uuid_iterator: Iterator | None
) -> HydratedReport:
    if asset_reports is None:
        asset_reports = []

    return HydratedReport(
        report_recipe=recipe.reference,
        name=name,
        report_type=report_type,
        template=template,
        date_generated=datetime(2024, 1, 1, 23, 59, 59, 999999),
        reference_date=datetime(2024, 1, 1, 23, 59, 59, 999999),
        input_oois=asset_reports,
        organization_code="test",
        organization_name="Test Organization",
        organization_tags=[],
        data_raw_id=str(next(uuid_iterator)),
        observed_at=datetime(2024, 1, 1, 23, 59, 59, 999999),
    )


ids = iter(
    [
        UUID("acbd2250-85f4-471a-ab70-ba1750280194"),
        UUID("ba2d86b8-aca8-4009-adc0-e3d59ea34904"),
        UUID("3d2ea955-13c1-46f6-81f3-edfe72d8af0b"),
        UUID("fe4d0f5d-5447-47d3-952d-74544c8a9d8d"),
        UUID("3ca35c20-1139-4bf4-a11a-a0b83f3c48ff"),
        UUID("1e419bee-672f-4561-b3b9-f47bd6ce60b7"),
        UUID("1e419bee-672f-4561-b3b9-f47bd6ce60b7"),
    ]
)


assets = [
    create_asset_report("RPKI Report", "rpki-report", "rpki_report/report.html", ids),
    create_asset_report(
        "Safe Connections Report", "safe-connections-report", "safe_connections_report/report.html", ids
    ),
    create_asset_report("System Report", "systems-report", "systems_report/report.html", ids),
    create_asset_report("Mail Report", "mail-report", "mail_report/report.html", ids),
    create_asset_report("IPv6 Report", "ipv6-report", "ipv6_report/report.html", ids),
    create_asset_report("Web System Report", "web-system-report", "web_system_report/report.html", ids),
    create_asset_report("Web System Report", "web-system-report", "web_system_report/report.html", ids),
]

dns_report = create_asset_report(
    "DNS Report", "dns-report", "dns_report/report.html", iter(["a5ccf97b-d4e9-442d-85bf-84e739b63da9s"])
)


@pytest.fixture
def report_list_one_asset_report():
    uuids = iter(["acbd2250-85f4-471a-ab70-ba17502801e"])
    return [create_report("Concatenated test report", "concatenated-report", "report.html", [assets[0]], uuids)]


@pytest.fixture
def report_list_two_asset_reports():
    uuids = iter(["acbd2250-85f4-471a-ab70-ba17502801a"])
    return [
        create_report("Concatenated test report", "concatenated-report", "report.html", [assets[5], assets[6]], uuids)
    ]


@pytest.fixture
def report_list_six_asset_reports():
    uuids = iter(["acbd2250-85f4-471a-ab70-ba17502801a"])
    asset_reports = [assets[0], assets[1], assets[2], assets[3], assets[4], assets[5]]
    return [create_report("Concatenated test report", "concatenated-report", "report.html", asset_reports, uuids)]


@pytest.fixture
def get_asset_reports() -> list[tuple[str, Report]]:
    return [
        (parent_report.primary_key, assets[0]),
        (parent_report.primary_key, assets[1]),
        (parent_report.primary_key, assets[2]),
        (parent_report.primary_key, assets[3]),
        (parent_report.primary_key, assets[4]),
        (parent_report.primary_key, assets[5]),
    ]


@pytest.fixture
def report_recipe():
    return ReportRecipe(
        report_type="concatenated-report",
        recipe_id="744d054e-9c70-4f18-ad27-122cfc1b7903",
        report_name_format="Test Report Name Format",
        input_recipe={"input_oois": ["Hostname|internet|mispo.es"]},
        asset_report_types=["dns-report"],
        cron_expression="0 0 * * *",
    )


def setup_request(request, user):
    request = SessionMiddleware(lambda r: r)(request)
    request.session[DEVICE_ID_SESSION_KEY] = user.staticdevice_set.get().persistent_id
    request = OTPMiddleware(lambda r: r)(request)
    request = MessageMiddleware(lambda r: r)(request)

    request.user = user

    return request


@pytest.fixture
def mock_scheduler(mocker):
    return mocker.patch("rocky.views.scheduler.scheduler_client")()


def get_stub_path(file_name: str) -> Path:
    return Path(__file__).parent / "stubs" / file_name


def get_boefjes_data() -> list[dict]:
    return json.loads(get_stub_path("katalogus_boefjes.json").read_text())


def get_normalizers_data() -> list[dict]:
    return json.loads(get_stub_path("katalogus_normalizers.json").read_text())


def get_aggregate_report_data():
    return json.loads(get_stub_path("aggregate_report_data.json").read_text())


@pytest.fixture()
def get_multi_report_data_minvws():
    return json.loads(get_stub_path("multi_report_data_minvws.json").read_text())


@pytest.fixture()
def get_multi_report_data_mispoes():
    return json.loads(get_stub_path("multi_report_data_mispoes.json").read_text())


@pytest.fixture()
def get_multi_report_post_processed_data():
    return json.loads(get_stub_path("multi_report_post_processed_data.json").read_text())


def get_plugins_data() -> list[dict]:
    return get_boefjes_data() + get_normalizers_data()


@pytest.fixture()
def mock_mixins_katalogus(mocker):
    return mocker.patch("account.mixins.OrganizationView.get_katalogus")


@pytest.fixture()
def mock_katalogus_client(mocker):
    return mocker.patch("katalogus.client.KATalogusClient")


@pytest.fixture
def mock_scheduler_client_task_list(mock_scheduler):
    mock_scheduler_session = mock_scheduler._client
    response = Response(
        200,
        content=(
            json.dumps(
                {
                    "count": 1,
                    "next": "http://scheduler:8000/tasks?scheduler_id=boefje-test&type=boefje&plugin_id=test_plugin&limit=10&offset=10",
                    "previous": None,
                    "results": [
                        {
                            "id": "2e757dd3-66c7-46b8-9987-7cd18252cc6d",
                            "hash": "416aa907e0b2a16c1b324f7d3261c5a4",
                            "scheduler_id": "boefje-test",
                            "schedule_id": None,
                            "type": "boefje",
                            "priority": 631,
                            "data": {
                                "id": "2e757dd366c746b899877cd18252cc6d",
                                "boefje": {"id": "test-plugin", "version": None},
                                "input_ooi": "Hostname|internet|example.com",
                                "organization": "test",
                                "dispatches": [],
                            },
                            "status": "completed",
                            "created_at": "2023-05-09T09:37:20.909069+00:00",
                            "modified_at": "2023-05-09T09:37:20.909071+00:00",
                        }
                    ],
                }
            ).encode()
        ),
    )

    mock_scheduler_session.get.return_value = response

    return mock_scheduler_session


class MockOctopoesAPIConnector:
    oois: dict[Reference, OOI]
    queries: dict[str, dict[Reference | str | None, list[OOI]]]
    valid_time: datetime

    def __init__(self, valid_time: datetime):
        self.valid_time = valid_time

    def get(self, reference: Reference, valid_time: datetime | None = None) -> OOI:
        return self.oois[reference]

    def get_tree(
        self, reference: Reference, valid_time: datetime, types: set = frozenset(), depth: int = 1
    ) -> ReferenceTree:
        return self.tree[reference]

    def query(
        self, path: str, valid_time: datetime, source: Reference | str | None = None, offset: int = 0, limit: int = 50
    ) -> list[OOI]:
        return self.queries[path][source]

    def query_many(
        self, path: str, valid_time: datetime, sources: list[OOI | Reference | str]
    ) -> list[tuple[str, OOIType]]:
        result = []

        for source in sources:
            for ooi in self.queries[path][str(source)]:
                result.append((str(source), ooi))

        return result

    def get_history(self, reference: Reference) -> list[TransactionRecord]:
        return [
            TransactionRecord(
                txTime=self.valid_time,
                txId=287,
                validTime=self.valid_time,
                contentHash="636a28da4792b9f5007143bb35bd37d48662df9b",
            )
        ]

    def list_origins(
        self,
        valid_time: datetime | None = None,
        source: Reference | None = None,
        result: Reference | None = None,
        task_id: UUID | None = None,
        origin_type: OriginType | None = None,
    ) -> list[Origin]:
        return []

    def list_objects(
        self,
        types: set[type[OOI]],
        valid_time: datetime,
        offset: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        scan_level: set[ScanLevel] = DEFAULT_SCAN_LEVEL_FILTER,
        scan_profile_type: set[ScanProfileType] = DEFAULT_SCAN_PROFILE_TYPE_FILTER,
    ) -> Paginated[OOIType]:
        return Paginated[OOIType](items=list(self.oois.values()), count=len(self.oois))


@pytest.fixture
def mock_octopoes_api_connector(valid_time):
    return MockOctopoesAPIConnector(valid_time)


@pytest.fixture
def listed_hostnames(network) -> list[Hostname]:
    return [
        Hostname(network=network.reference, name="example.com"),
        Hostname(network=network.reference, name="a.example.com"),
        Hostname(network=network.reference, name="b.example.com"),
        Hostname(network=network.reference, name="c.example.com"),
        Hostname(network=network.reference, name="d.example.com"),
        Hostname(network=network.reference, name="e.example.com"),
        Hostname(network=network.reference, name="f.example.com"),
    ]


@pytest.fixture
def paginated_task_list(task):
    return PaginatedTasksResponse(count=1, next="", previous=None, results=[task])


@pytest.fixture
def reports_more_input_oois():
    uuids = iter([f"acbd2250-85f4-471a-ab70-ba175028019{i}" for i in range(1, 9)])
    references = [f"Hostname|internet|example{i}.com" for i in range(1, 9)]
    sc_name = "Safe Connections Report"

    return create_report(
        "Test Parent Report",
        "concatenated-report",
        "report.html",
        [
            create_asset_report("RPKI Report", "rpki-report", "rpki_report/report.html", uuids, references[0]),
            create_asset_report("RPKI Report", "rpki-report", "rpki_report/report.html", uuids, references[1]),
            create_asset_report("RPKI Report", "rpki-report", "rpki_report/report.html", uuids, references[2]),
            create_asset_report("RPKI Report", "rpki-report", "rpki_report/report.html", uuids, references[3]),
            create_asset_report(
                sc_name, "safe-connections-report", "safe_connections_report/report.html", uuids, references[4]
            ),
            create_asset_report(
                sc_name, "safe-connections-report", "safe_connections_report/report.html", uuids, references[5]
            ),
            create_asset_report(
                sc_name, "safe-connections-report", "safe_connections_report/report.html", uuids, references[6]
            ),
            create_asset_report(
                sc_name, "safe-connections-report", "safe_connections_report/report.html", uuids, references[7]
            ),
        ],
        iter(["a5ccf97b-d4e9-442d-85bf-84e739b6d3ed"]),
    )


@pytest.fixture
def rocky_health():
    ServiceHealth(
        service="rocky",
        healthy=True,
        version="0.0.1.dev1",
        additional=None,
        results=[
            ServiceHealth(
                service="octopoes",
                healthy=True,
                version="0.0.1.dev1",
                additional=None,
                results=[
                    ServiceHealth(
                        service="xtdb",
                        healthy=True,
                        version="1.24.1",
                        additional={
                            "version": "1.24.1",
                            "revision": "1164f9a3c7e36edbc026867945765fd4366c1731",
                            "indexVersion": 22,
                            "consumerState": None,
                            "kvStore": "xtdb.rocksdb.RocksKv",
                            "estimateNumKeys": 24552,
                            "size": 24053091,
                        },
                        results=[],
                    )
                ],
            ),
            ServiceHealth(service="katalogus", healthy=True, version="0.0.1-development", additional=None, results=[]),
            ServiceHealth(service="scheduler", healthy=True, version="0.0.1.dev1", additional=None, results=[]),
            ServiceHealth(service="bytes", healthy=True, version="0.0.1.dev1", additional=None, results=[]),
        ],
    )


@pytest.fixture
def boefje_dns_records():
    return Boefje(
        type="boefje",
        id="dns-records",
        name="DnsRecords",
        description="Fetch the DNS record(s) of a hostname",
        enabled=True,
        scan_level=SCAN_LEVEL.L1,
        consumes={Hostname},
        produces={"boefje/dns-records"},
        boefje_schema={},
        oci_image="ghcr.io/test/image:123",
        oci_arguments=["-test", "-arg"],
    )


@pytest.fixture
def boefje_nmap_tcp():
    return Boefje(
        type="boefje",
        id="nmap",
        name="Nmap TCP",
        description="Defaults to top 250 TCP ports. Includes service detection.",
        enabled=True,
        scan_level=SCAN_LEVEL.L2,
        consumes={IPAddressV4, IPAddressV6},
        produces={"boefje/nmap"},
        boefje_schema={},
        oci_image="ghcr.io/test/image:123",
        oci_arguments=["-test", "-arg"],
    )


@pytest.fixture
def drf_admin_client(create_drf_client, admin_user):
    client = create_drf_client(admin_user)
    # We need to set this so that the test client doesn't throw an
    # exception, but will return error in the API we can test
    client.raise_request_exception = False
    return client


@pytest.fixture
def drf_redteam_client(create_drf_client, redteamuser):
    client = create_drf_client(redteamuser)
    # We need to set this so that the test client doesn't throw an
    # exception, but will return error in the API we can test
    client.raise_request_exception = False
    return client


@pytest.fixture
def get_aggregate_report_ooi():
    return HydratedReport(
        scan_profile=EmptyScanProfile(
            scan_profile_type="empty",
            reference=Reference("Report|6a073ba0-46d3-451c-a7f8-46923c2b841b"),
            level=ScanLevel.L0,
        ),
        name="Aggregate Report",
        report_type="aggregate-organisation-report",
        template="aggregate_organisation_report/report.html",
        date_generated=datetime(2024, 9, 3, 14, 14, 46, 999999),
        input_oois=[],
        organization_code="_test",
        organization_name="Test Organization",
        organization_tags=[],
        data_raw_id="250cf43e-bfe2-4249-b493-a12921cb79f6",
        observed_at=datetime(2024, 9, 3, 14, 14, 45, 999999),
        reference_date=datetime(2024, 9, 3, 14, 14, 45, 999999),
        report_recipe=recipe.reference,
    )


@pytest.fixture
def get_aggregate_report_from_bytes():
    data = {
        "systems": {
            "services": {
                "IPAddressV4|internet|134.209.85.72": {"hostnames": ["Hostname|internet|mispo.es"], "services": []}
            }
        },
        "services": {},
        "recommendations": [],
        "recommendation_counts": {},
        "open_ports": {"134.209.85.72": {"ports": {}, "hostnames": ["mispo.es"], "services": {}}},
        "ipv6": {"mispo.es": {"enabled": False, "systems": []}},
        "vulnerabilities": {
            "IPAddressV4|internet|134.209.85.72": {
                "hostnames": "(mispo.es)",
                "vulnerabilities": {},
                "summary": {"total_findings": 0, "total_criticals": 0, "terms": [], "recommendations": []},
                "title": "134.209.85.72",
            }
        },
        "basic_security": {
            "rpki": {},
            "system_specific": {"Mail": [], "Web": [], "DNS": []},
            "safe_connections": {},
            "summary": {},
        },
        "summary": {"critical_vulnerabilities": 0, "ips_scanned": 1, "hostnames_scanned": 1, "terms_in_report": ""},
        "total_findings": 0,
        "total_systems": 1,
        "total_hostnames": 1,
        "total_systems_basic_security": 0,
        "health": [
            {"service": "rocky", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {"service": "octopoes", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {
                "service": "xtdb",
                "healthy": True,
                "version": "1.24.1",
                "additional": {
                    "version": "1.24.1",
                    "revision": "1164f9a3c7e36edbc026867945765fd4366c1731",
                    "indexVersion": 22,
                    "consumerState": None,
                    "kvStore": "xtdb.rocksdb.RocksKv",
                    "estimateNumKeys": 36846,
                    "size": 33301692,
                },
                "results": [],
            },
            {
                "service": "katalogus",
                "healthy": True,
                "version": "0.0.1-development",
                "additional": None,
                "results": [],
            },
            {"service": "scheduler", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {"service": "bytes", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
        ],
        "config_oois": [],
        "input_data": {
            "input_oois": ["Hostname|internet|mispo.es"],
            "report_types": [
                "ipv6-report",
                "mail-report",
                "name-server-report",
                "open-ports-report",
                "rpki-report",
                "safe-connections-report",
                "systems-report",
                "vulnerability-report",
                "web-system-report",
            ],
            "plugins": {"required": [], "optional": []},
        },
    }
    return json.dumps(data).encode("utf-8")


@pytest.fixture
def report_data_ooi_org_a(organization, get_multi_report_data_minvws):
    return ReportData(
        scan_profile=EmptyScanProfile(
            scan_profile_type="empty", reference=Reference(f"ReportData|{organization.code}"), level=ScanLevel.L0
        ),
        organization_code=organization.code,
        organization_name=organization.name,
        organization_tags=[],
        data=get_multi_report_data_minvws,
    )


@pytest.fixture
def report_data_ooi_org_b(organization_b, get_multi_report_data_mispoes):
    return ReportData(
        scan_profile=EmptyScanProfile(
            scan_profile_type="empty", reference=Reference(f"ReportData|{organization_b.code}"), level=ScanLevel.L0
        ),
        organization_code=organization_b.code,
        organization_name=organization_b.name,
        organization_tags=[],
        data=get_multi_report_data_mispoes,
    )


@pytest.fixture
def multi_report_ooi(report_data_ooi_org_a, report_data_ooi_org_b):
    reports = [
        create_asset_report("test", "test", "test", iter(["7b305f0d-c0a7-4ad5-af1e-31f81fc229c2"])),
        create_asset_report("test", "test", "test", iter(["7b305f0d-c0a7-4ad5-af1e-31f81fc229c3"])),
    ]
    return HydratedReport(
        name="Sector Report",
        report_type="multi-organization-report",
        template="multi_organization_report/report.html",
        date_generated=datetime(2024, 10, 18, 14, 14, 46, 999999),
        input_oois=reports,
        organization_code=report_data_ooi_org_a.organization_code,
        organization_name=report_data_ooi_org_a.organization_name,
        organization_tags=[],
        data_raw_id="bb4d5271-b273-4af4-a25a-83ba0c4fed63",
        observed_at=datetime(2024, 10, 18, 14, 14, 45, 999999),
        reference_date=datetime(2024, 10, 18, 14, 14, 45, 999999),
        report_recipe=recipe.reference,
    )


@pytest.fixture
def report_list():
    asset_ids = iter(
        [
            "27e8fa60-4675-4c22-b7a7-76152fc520b8",
            "775d62df-edf9-4c19-91cc-2cc1586a8111",
            "6ea4268f-f8c9-4ccd-9f81-efb2bf60b215",
            "fa648efe-7724-41cd-96c0-2c0d48b631bc",
            "d2623e9f-3f56-4c4f-b01c-abf4a6f5794d",
            "ba8e864a-770f-4a18-90d4-d7b8fba054ac",
            "771190cb-a570-4ddf-bf10-2b7cb6d7b852",
            "ef007438-6266-40c5-981b-a59a5e59d2a4",
            "e545a488-de8a-4750-8056-6a3b354d011f",
            "af8c8999-530d-45d5-a8b8-c823ee3c24b7",
            "7b305f0d-c0a7-4ad5-af1e-31f81fc229c2",
        ]
    )

    def asset_report(name, report_type, template):
        return create_asset_report(name, report_type, template, asset_ids, "Hostname|internet|minvws.nl")

    asset_reports = [
        asset_report(
            "Safe Connections Report for minvws.nl", "safe-connections-report", "safe_connections_report/report.html"
        ),
        asset_report("DNS Report for minvws.nl", "dns-report", "dns_report/report.html"),
        asset_report("Name Server Report for minvws.nl", "name-server-report", "name_server_report/report.html"),
        asset_report("Vulnerability Report for minvws.nl", "vulnerability-report", "vulnerability_report/report.html"),
        asset_report("Web System Report for minvws.nl", "web-system-report", "web_system_report/report.html"),
        asset_report("Mail Report for minvws.nl", "mail-report", "mail_report/report.html"),
        asset_report("System Report for minvws.nl", "systems-report", "systems_report/report.html"),
        asset_report("IPv6 Report for minvws.nl", "ipv6-report", "ipv6_report/report.html"),
        asset_report("Open Ports Report for minvws.nl", "open-ports-report", "open_ports_report/report.html"),
        asset_report("Findings Report for minvws.nl", "findings-report", "findings_report/report.html"),
        asset_report("RPKI Report for minvws.nl", "rpki-report", "rpki_report/report.html"),
    ]

    return Paginated(
        count=3,
        items=[
            create_report(
                "Concatenated Report for minvws.nl",
                "concatenated-report",
                "report.html",
                [
                    create_asset_report(
                        "Findings Report for minvws.nl",
                        "findings-report",
                        "findings_report/report.html",
                        iter(["3300354d-530f-4ecf-8485-e120f43ba3f1"]),
                        "Hostname|internet|minvws.nl",
                    )
                ],
                iter(["3300354d-530f-4ecf-8485-e120f43ba3f1"]),
            ),
            create_report(
                "Aggregate Report",
                "aggregate-organisation-report",
                "aggregate_organisation_report/report.html",
                [],
                iter(["7e888ca9-cebc-4d6e-9f2c-5b45fa7101d4"]),
            ),
            create_report(
                "Concatenated Report for minvws.nl",
                "concatenated-report",
                "report.html",
                asset_reports,
                iter(["eb5c1226-7ab0-4e3f-8b41-7ab7016fa3fd"]),
            ),
        ],
    )


@pytest.fixture
def get_report_input_data_from_bytes():
    input_data = {
        "input_data": {
            "input_oois": ["Hostname|internet|minvws.nl"],
            "report_types": [
                "ipv6-report",
                "mail-report",
                "name-server-report",
                "open-ports-report",
                "rpki-report",
                "safe-connections-report",
                "systems-report",
                "vulnerability-report",
                "web-system-report",
            ],
            "plugins": {
                "required": [
                    "rpki",
                    "webpage-analysis",
                    "ssl-certificates",
                    "security_txt_downloader",
                    "testssl-sh-ciphers",
                    "dns-records",
                    "dns-sec",
                    "ssl-version",
                    "nmap",
                ],
                "optional": ["masscan", "shodan", "nmap-ip-range", "nmap-udp", "nmap-ports"],
            },
        }
    }
    return json.dumps(input_data).encode("utf-8")


@pytest.fixture
def aggregate_report_with_sub_reports():
    ids = iter(
        [
            "a534b4d5-5dba-4ddc-9b77-970675ae4b1c",
            "0bdea8eb-7ac0-46ef-ad14-ea3b0bfe1030",
            "53d5452c-9e67-42d2-9cb0-3b684d8967a2",
            "a218ca79-47de-4473-a93d-54d14baadd98",
            "3779f5b0-3adf-41c8-9630-8eed8a857ae6",
            "851feeab-7036-48f6-81ef-599467c52457",
            "1e259fce-3cd7-436f-b233-b4ae24a8f11b",
            "50a9e4df-3b69-4ad8-b798-df626162db5a",
            "5faa3364-c8b2-4b9c-8cc8-99d8f19ccf8a",
        ]
    )

    def asset_report(name: str, report_type: str, template: str):
        return create_asset_report(name, report_type, template, ids, "Hostname|internet|mispo.es", "_rieven", "Rieven")

    aggregate_report = HydratedReport(
        name="Aggregate Report",
        report_type="aggregate-organisation-report",
        template="aggregate_organisation_report/report.html",
        date_generated=datetime(2024, 11, 21, 10, 7, 7, 441137),
        input_oois=[
            asset_report("Mail Report", "mail-report", "mail_report/report.html"),
            asset_report("IPv6 Report", "ipv6-report", "ipv6_report/report.html"),
            asset_report("RPKI Report", "rpki-report", "rpki_report/report.html"),
            asset_report("Web System Report", "web-system-report", "web_system_report/report.html"),
            asset_report("Open Ports Report", "open-ports-report", "open_ports_report/report.html"),
            asset_report("Vulnerability Report", "vulnerability-report", "vulnerability_report/report.html"),
            asset_report("System Report", "systems-report", "systems_report/report.html"),
            asset_report("Name Server Report", "name-server-report", "name_server_report/report.html"),
        ],
        organization_code="_rieven",
        organization_name="Rieven",
        organization_tags=[],
        data_raw_id="3a362cd7-6348-4e91-8a6f-4cd83f9f6a83",
        observed_at=datetime(2024, 11, 21, 10, 7, 7, 441043),
        reference_date=datetime(2024, 11, 21, 10, 7, 7, 441043),
        report_recipe=recipe.reference,
    )

    return Paginated(count=1, items=[aggregate_report])


@pytest.fixture
def reports_task_list():
    return PaginatedTasksResponse(
        count=2,
        next=None,
        previous=None,
        results=[
            Task(
                id=UUID("7f9d5b00-dbab-45f3-93a6-dd44cc20c359"),
                scheduler_id="report-_rieven",
                schedule_id="86032b20-f7ae-4a48-9093-87ec5a56e939",
                organisation="test",
                priority=1738747928,
                status=TaskStatus.FAILED,
                type="report",
                hash="8f73ee4346118b7814711eba8ebb13d8",
                data=ReportTask(
                    type="report", organisation_id="_rieven", report_recipe_id="3f5c1a46-1969-49b7-b402-4676fb59ca4b"
                ),
                created_at=datetime(2025, 2, 5, 9, 32, 8, 325523),
                modified_at=datetime(2025, 2, 5, 9, 32, 8, 325526),
            ),
            Task(
                id=UUID("9e23611d-36c2-4972-82f0-077bcb1a8941"),
                scheduler_id="report-_rieven",
                schedule_id="bd821e6e-6680-4215-8557-e049deeb0175",
                organisation="test 2",
                priority=1738684879,
                status=TaskStatus.COMPLETED,
                type="report",
                hash="5fc17aa4a8ff4874203446a106b4d5bb",
                data=ReportTask(
                    type="report", organisation_id="_rieven", report_recipe_id="451a676d-91f8-4366-ac24-d1a47205181d"
                ),
                created_at=datetime(2025, 2, 4, 16, 1, 19, 951925),
                modified_at=datetime(2025, 2, 4, 16, 1, 19, 951927),
            ),
        ],
    )


@pytest.fixture
def findings_dashboard_item(client_member, client_member_b):
    # make sure that no dashboards exist to test this particular set
    Dashboard.objects.all().delete()  # deleting dashboard deletes DashboardItem as well

    recipe_id_a = "7ebcdb32-e7f2-4c2d-840a-d7b8e6b37616"
    recipe_id_b = "c41bbf9a-7102-4b6b-b256-b3036e106316"

    dashboard_a = Dashboard.objects.create(name="Findings Dashboard", organization=client_member.organization)
    dashboard_b = Dashboard.objects.create(name="Findings Dashboard", organization=client_member_b.organization)

    dashboard_item_a = DashboardItem.objects.create(dashboard=dashboard_a, recipe=recipe_id_a, findings_dashboard=True)
    dashboard_item_b = DashboardItem.objects.create(dashboard=dashboard_b, recipe=recipe_id_b, findings_dashboard=True)

    return [dashboard_item_a, dashboard_item_b]


@pytest.fixture
def findings_reports(client_member, client_member_b):
    bytes_raw_id_a = "62258c3d-89b2-4fde-a2e0-d78715a174e6"
    bytes_raw_id_b = "1b887350-0afb-4786-b587-4323cd8e4180"

    recipe_id_a = "7ebcdb32-e7f2-4c2d-840a-d7b8e6b37616"
    recipe_id_b = "c41bbf9a-7102-4b6b-b256-b3036e106316"

    asset_report_a = create_asset_report(
        name="Findings Report for mispo.es",
        report_type=FindingsReport.id,
        template=FindingsReport.template_path,
        uuid_iterator=iter(["a5ccf97b-d4e9-442d-85bf-84e739b63da9s"]),
    )

    asset_report_b = create_asset_report(
        name="Findings Report for mispo.es",
        report_type=FindingsReport.id,
        template=FindingsReport.template_path,
        uuid_iterator=iter(["a5ccf97b-d4e9-442d-85bf-84e739b63da9l"]),
    )

    report_a = HydratedReport(
        object_type="HydratedReport",
        scan_profile=None,
        user_id=None,
        primary_key="Report|9a0fd1f4-ba2b-4800-ade8-7f17f099e179",
        name="Crisis Room Aggregate Report",
        report_type="aggregate-organisation-report",
        template="aggregate_organisation_report/report.html",
        date_generated=datetime(2024, 12, 23, 12, 0, 32, 730678),
        reference_date=datetime(2024, 12, 23, 12, 0, 32, 730678),
        input_oois=[asset_report_a],
        report_id=UUID("9a0fd1f4-ba2b-4800-ade8-7f17f099e179"),
        organization_code=client_member.organization.code,
        organization_name=client_member.organization.name,
        organization_tags=[],
        data_raw_id=bytes_raw_id_a,
        observed_at=datetime(2024, 12, 23, 12, 0, 32, 53194),
        parent_report=None,
        report_recipe=Reference(recipe_id_a),
        has_parent=False,
    )

    report_b = HydratedReport(
        object_type="HydratedReport",
        scan_profile=None,
        user_id=None,
        primary_key="Report|2b871ed0-44e5-4375-85af-4a1cf44145f7",
        name="Crisis Room Aggregate Report",
        report_type="aggregate-organisation-report",
        template="aggregate_organisation_report/report.html",
        date_generated=datetime(2024, 12, 23, 11, 0, 32, 447950),
        reference_date=datetime(2024, 12, 23, 11, 0, 32, 447950),
        input_oois=[asset_report_b],
        report_id=UUID("2b871ed0-44e5-4375-85af-4a1cf44145f7"),
        organization_code=client_member_b.organization.code,
        organization_name=client_member_b.organization.name,
        organization_tags=[],
        data_raw_id=bytes_raw_id_b,
        observed_at=datetime(2024, 12, 23, 11, 0, 31, 602127),
        parent_report=None,
        report_recipe=Reference(recipe_id_b),
        has_parent=False,
    )

    return {recipe_id_a: report_a, recipe_id_b: report_b}


@pytest.fixture
def findings_reports_data():
    bytes_raw_id_a = "62258c3d-89b2-4fde-a2e0-d78715a174e6"
    bytes_raw_id_b = "1b887350-0afb-4786-b587-4323cd8e4180"

    report_data_a = {
        "systems": {"services": {}},
        "services": {},
        "recommendations": [],
        "recommendation_counts": {},
        "open_ports": {},
        "ipv6": {},
        "vulnerabilities": {},
        "findings": {
            "finding_types": [],
            "summary": {
                "total_by_severity_per_finding_type": {
                    "critical": 0,
                    "high": 0,
                    "medium": 3,
                    "low": 1,
                    "recommendation": 0,
                    "pending": 0,
                    "unknown": 0,
                },
                "total_by_severity": {
                    "critical": 0,
                    "high": 0,
                    "medium": 4,
                    "low": 3,
                    "recommendation": 0,
                    "pending": 0,
                    "unknown": 0,
                },
                "total_finding_types": 4,
                "total_occurrences": 7,
            },
        },
        "basic_security": {
            "rpki": {},
            "system_specific": {"Mail": [], "Web": [], "DNS": []},
            "safe_connections": {},
            "summary": {},
        },
        "summary": {"critical_vulnerabilities": 0, "ips_scanned": 0, "hostnames_scanned": 0, "terms_in_report": ""},
        "total_findings": 0,
        "total_systems": 0,
        "total_hostnames": 0,
        "total_systems_basic_security": 0,
        "health": [
            {"service": "rocky", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {"service": "octopoes", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {
                "service": "xtdb",
                "healthy": True,
                "version": "1.24.4",
                "additional": {
                    "version": "1.24.4",
                    "revision": "b46e92df67699cb25f3b21a61742c79da564b3b0",
                    "indexVersion": 22,
                    "consumerState": None,
                    "kvStore": "xtdb.rocksdb.RocksKv",
                    "estimateNumKeys": 56338,
                    "size": 93781419,
                },
                "results": [],
            },
            {
                "service": "katalogus",
                "healthy": True,
                "version": "0.0.1-development",
                "additional": None,
                "results": [],
            },
            {"service": "scheduler", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {"service": "bytes", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {"service": "keiko", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
        ],
        "config_oois": [],
        "input_data": {
            "input_oois": ["Hostname|internet|mispo.es"],
            "report_types": ["systems-report", "findings-report"],
            "plugins": {
                "required": [
                    "nmap",
                    "webpage-analysis",
                    "ssl-certificates",
                    "nmap-udp",
                    "ssl-version",
                    "testssl-sh-ciphers",
                    "dns-records",
                ],
                "optional": ["leakix", "snyk", "service_banner", "shodan"],
            },
        },
    }

    report_data_b = {
        "systems": {"services": {}},
        "services": {},
        "recommendations": [],
        "recommendation_counts": {},
        "open_ports": {},
        "ipv6": {},
        "vulnerabilities": {},
        "findings": {
            "finding_types": [],
            "summary": {
                "total_by_severity_per_finding_type": {
                    "critical": 1,
                    "high": 2,
                    "medium": 4,
                    "low": 2,
                    "recommendation": 1,
                    "pending": 1,
                    "unknown": 1,
                },
                "total_by_severity": {
                    "critical": 3,
                    "high": 3,
                    "medium": 5,
                    "low": 3,
                    "recommendation": 1,
                    "pending": 1,
                    "unknown": 1,
                },
                "total_finding_types": 12,
                "total_occurrences": 17,
            },
        },
        "basic_security": {
            "rpki": {},
            "system_specific": {"Mail": [], "Web": [], "DNS": []},
            "safe_connections": {},
            "summary": {},
        },
        "summary": {"critical_vulnerabilities": 0, "ips_scanned": 0, "hostnames_scanned": 0, "terms_in_report": ""},
        "total_findings": 0,
        "total_systems": 0,
        "total_hostnames": 0,
        "total_systems_basic_security": 0,
        "health": [
            {"service": "rocky", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {"service": "octopoes", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {
                "service": "xtdb",
                "healthy": True,
                "version": "1.24.4",
                "additional": {
                    "version": "1.24.4",
                    "revision": "b46e92df67699cb25f3b21a61742c79da564b3b0",
                    "indexVersion": 22,
                    "consumerState": None,
                    "kvStore": "xtdb.rocksdb.RocksKv",
                    "estimateNumKeys": 54693,
                    "size": 91850532,
                },
                "results": [],
            },
            {
                "service": "katalogus",
                "healthy": True,
                "version": "0.0.1-development",
                "additional": None,
                "results": [],
            },
            {"service": "scheduler", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {"service": "bytes", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
            {"service": "keiko", "healthy": True, "version": "0.0.1.dev1", "additional": None, "results": []},
        ],
        "config_oois": [],
        "input_data": {
            "input_oois": ["Hostname|internet|mispo.es"],
            "report_types": ["systems-report", "findings-report"],
            "plugins": {
                "required": [
                    "nmap",
                    "webpage-analysis",
                    "ssl-certificates",
                    "nmap-udp",
                    "ssl-version",
                    "testssl-sh-ciphers",
                    "dns-records",
                ],
                "optional": ["leakix", "snyk", "service_banner", "shodan"],
            },
        },
    }

    return {bytes_raw_id_a: report_data_a, bytes_raw_id_b: report_data_b}


@pytest.fixture
def findings_results(mocker, findings_dashboard_item, findings_reports, findings_reports_data):
    octopoes_client = mocker.patch("crisis_room.views.OctopoesAPIConnector")
    bytes_client = mocker.patch("crisis_room.views.get_bytes_client")

    octopoes_client().bulk_list_reports.return_value = findings_reports
    bytes_client().get_raws_all.return_value = findings_reports_data

    return DashboardService().get_dashboard_items(findings_dashboard_item)


@pytest.fixture
def expected_findings_results(findings_dashboard_item, findings_reports, findings_reports_data):
    findings_dashboard = []

    for index, data in enumerate(findings_dashboard_item):
        dashboard_item = DashboardItemView()
        dashboard_item.item = data
        report = findings_reports[data.recipe]
        report_data = findings_reports_data[report.data_raw_id]

        dashboard_item.data = {"report": report, "report_data": report_data | {"highest_risk_level": ""}}
        findings_dashboard.append(dashboard_item)

    return findings_dashboard


@pytest.fixture
def scheduled_report_recipe():
    return ReportRecipe(
        object_type="ReportRecipe",
        scan_profile=EmptyScanProfile(
            scan_profile_type="empty",
            reference=Reference("ReportRecipe|3fed7d00-6261-4ad1-b08f-9b91434aa41e"),
            level=ScanLevel.L0,
            user_id=None,
        ),
        user_id=None,
        primary_key="ReportRecipe|3fed7d00-6261-4ad1-b08f-9b91434aa41e",
        recipe_id=UUID("3fed7d00-6261-4ad1-b08f-9b91434aa41e"),
        report_name_format="${report_type} for ${oois_count} objects",
        input_recipe={"input_oois": ["Hostname|internet|mispo.es"]},
        report_type="concatenated-report",
        asset_report_types=[
            "dns-report",
            "findings-report",
            "ipv6-report",
            "mail-report",
            "name-server-report",
            "open-ports-report",
            "rpki-report",
            "safe-connections-report",
            "systems-report",
            "vulnerability-report",
            "web-system-report",
        ],
        cron_expression=None,
    )


@pytest.fixture
def scheduled_reports_list():
    return [
        ScheduleResponse(
            id=UUID("7706ebc1-b24b-44fb-a7b3-9a44d80b2644"),
            scheduler_id="report",
            organisation="test",
            hash="bb5708d2f82e11cc5cda3aef54190f2e",
            data={
                "type": "report",
                "organisation_id": "_rieven",
                "report_recipe_id": "3fed7d00-6261-4ad1-b08f-9b91434aa41e",
            },
            enabled=True,
            schedule=None,
            deadline_at=None,
            created_at=datetime(2025, 2, 12, 16, 1, 19, 951925),
            modified_at=datetime(2025, 2, 12, 16, 1, 19, 951925),
        )
    ]


@pytest.fixture
def dashboard_items(redteam_member):
    # first delete to test that no other dashboard and items exists
    Dashboard.objects.all().delete()

    dashboard = Dashboard.objects.create(name="Test", organization=redteam_member.organization)
    dashboard_item_1 = DashboardItem.objects.create(
        dashboard=dashboard,
        name="URLs",
        source="object_list",
        query='{"observed_at":"2015-06-06", "ooi_type": ["URL"], "clearance_level": [], "clearance_type": [],'
        '"search": "", "order_by": "object_type", "sorting_order": "asc", "limit": 20}',
        settings={
            "size": "1",
            "columns": {
                "object": "Object",
                "object_type": "Type",
                "clearance_type": "Clearance type",
                "clearance_level": "Clearance level",
            },
        },
        display_in_dashboard=True,
    )
    dashboard_item_2 = DashboardItem.objects.create(
        dashboard=dashboard,
        name="Hostnames",
        source="object_list",
        query='{"observed_at":"2015-06-06", "ooi_type": ["Hostname"], "clearance_level": [], "clearance_type": [],'
        '"search": "", "order_by": "object_type", "sorting_order": "asc", "limit": 20}',
        settings={
            "size": "1",
            "columns": {
                "object": "Object",
                "object_type": "Type",
                "clearance_type": "Clearance type",
                "clearance_level": "Clearance level",
            },
        },
        display_in_dashboard=True,
    )
    dashboard_item_3 = DashboardItem.objects.create(
        dashboard=dashboard,
        name="IPs",
        source="object_list",
        query='{"observed_at":"2015-06-06", "ooi_type": ["IPAddress"], "clearance_level": [], "clearance_type": [],'
        '"search": "", "order_by": "object_type", "sorting_order": "asc", "limit": 20}',
        settings={
            "size": "1",
            "columns": {
                "object": "Object",
                "object_type": "Type",
                "clearance_type": "Clearance type",
                "clearance_level": "Clearance level",
            },
        },
        display_in_dashboard=True,
    )
    dashboard_item_4 = DashboardItem.objects.create(
        dashboard=dashboard,
        name="Networks",
        source="object_list",
        query='{"observed_at":"2015-06-06", "ooi_type": ["Network"], "clearance_level": [], "clearance_type": [],'
        '"search": "", "order_by": "object_type", "sorting_order": "asc", "limit": 20}',
        settings={
            "size": "1",
            "columns": {
                "object": "Object",
                "object_type": "Type",
                "clearance_type": "Clearance type",
                "clearance_level": "Clearance level",
            },
        },
        display_in_dashboard=True,
    )
    return [dashboard_item_1, dashboard_item_2, dashboard_item_3, dashboard_item_4]


@pytest.fixture
def dashboard_items_from_findings_list(redteam_member):
    # first delete to test that no other dashboard and items exists
    Dashboard.objects.all().delete()

    dashboard = Dashboard.objects.create(name="Test", organization=redteam_member.organization)

    dashboard_item_1 = DashboardItem.objects.create(
        dashboard=dashboard,
        name="Medium severity findings",
        source="findings_list",
        query='{"observed_at":"2015-06-06", "order_by": "score", "asc_desc": "asc", "limit": 5,'
        '"severities": ["medium"], "exclude_muted": true, "only_muted": false, "search_string": ""}',
        settings={
            "size": "2",
            "columns": {
                "tree": "Tree",
                "graph": "Graph",
                "finding": "Finding",
                "location": "Location",
                "severity": "Severity",
            },
        },
        display_in_dashboard=True,
    )

    return [dashboard_item_1]
