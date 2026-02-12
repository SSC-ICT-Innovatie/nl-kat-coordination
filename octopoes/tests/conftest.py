import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from ipaddress import IPv4Address, ip_address
from unittest.mock import Mock

import pytest
from bits.runner import BitRunner

from octopoes.config.settings import Settings
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.core.app import get_xtdb_client
from octopoes.core.service import OctopoesService
from octopoes.events.manager import EventManager
from octopoes.models import OOI, DeclaredScanProfile, EmptyScanProfile, Reference, ScanProfileBase
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddressV6
from octopoes.models.ooi.reports import AssetReport, Report, ReportRecipe
from octopoes.models.ooi.software import Software, SoftwareInstance
from octopoes.models.ooi.web import URL, HTTPHeader, SecurityTXT
from octopoes.models.origin import Origin, OriginType
from octopoes.models.path import Direction, Path
from octopoes.models.types import (
    DNSZone,
    Hostname,
    HostnameHTTPURL,
    HTTPResource,
    IPAddressV4,
    IPPort,
    IPService,
    Network,
    ResolvedHostname,
    Service,
    Website,
)
from octopoes.repositories.ooi_repository import OOIRepository, XTDBOOIRepository
from octopoes.repositories.origin_parameter_repository import XTDBOriginParameterRepository
from octopoes.repositories.origin_repository import XTDBOriginRepository
from octopoes.repositories.scan_profile_repository import ScanProfileRepository, XTDBScanProfileRepository
from octopoes.xtdb.client import XTDBHTTPClient, XTDBSession


@pytest.fixture
def valid_time():
    return datetime.now(timezone.utc)


class MockScanProfileRepository(ScanProfileRepository):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.profiles = {}

    def get(self, ooi_reference: Reference, valid_time: datetime) -> ScanProfileBase:
        return self.profiles[ooi_reference]

    def save(
        self, old_scan_profile: ScanProfileBase | None, new_scan_profile: ScanProfileBase, valid_time: datetime
    ) -> None:
        self.profiles[new_scan_profile.reference] = new_scan_profile

    def list_scan_profiles(self, scan_profile_type: str | None, valid_time: datetime) -> list[ScanProfileBase]:
        if scan_profile_type:
            return [profile for profile in self.profiles.values() if profile.scan_profile_type == scan_profile_type]
        else:
            return self.profiles.values()

    def delete(self, scan_profile: ScanProfileBase, valid_time: datetime) -> None:
        del self.profiles[scan_profile.reference]


@pytest.fixture
def scan_profile_repository():
    return MockScanProfileRepository(Mock())


class MockOOIRepository(OOIRepository):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.oois = {}

    def save(self, ooi: OOI, valid_time: datetime, end_valid_time: datetime | None = None) -> None:
        self.oois[ooi.reference] = ooi

    def load_bulk(self, references: set[Reference], valid_time: datetime) -> dict[str, OOI]:
        return {ooi.primary_key: ooi for ooi in self.oois.values() if ooi.reference in references}

    def list_neighbours(self, references: set[Reference], paths: set[Path], valid_time: datetime) -> set[OOI]:
        neighbours = set()

        for path in paths:
            # Neighbours should have paths of length 1
            assert len(path.segments) == 1
            segment = path.segments[0]
            if segment.direction == Direction.OUTGOING:
                for ref in references:
                    neighbour_ref = getattr(self.oois[ref], segment.property_name)
                    if neighbour_ref is not None:
                        neighbours.add(self.oois[neighbour_ref])
            else:
                for ooi in self.oois.values():
                    if not isinstance(ooi, segment.target_type):
                        continue

                    for ref in references:
                        if getattr(ooi, segment.property_name) == ref:
                            neighbours.add(ooi)

        return neighbours

    def list_oois_without_scan_profile(self, valid_time: datetime) -> set[Reference]:
        return set()


@pytest.fixture
def ooi_repository():
    return MockOOIRepository(Mock())


def add_ooi(ooi, ooi_repository, scan_profile_repository, valid_time):
    ooi_repository.save(ooi, valid_time)
    scan_profile_repository.save(None, EmptyScanProfile(reference=ooi.reference), valid_time)
    return ooi


@pytest.fixture
def network(ooi_repository, scan_profile_repository, valid_time):
    return add_ooi(Network(name="internet"), ooi_repository, scan_profile_repository, valid_time)


@pytest.fixture
def dns_zone(network, ooi_repository, hostname, scan_profile_repository, valid_time):
    ooi = add_ooi(
        DNSZone(name="example.com", hostname=hostname.reference, network=network.reference),
        ooi_repository,
        scan_profile_repository,
        valid_time,
    )
    hostname.dns_zone = ooi.reference
    return ooi


@pytest.fixture
def hostname(network, ooi_repository, scan_profile_repository, valid_time):
    return add_ooi(
        Hostname(name="example.com", network=network.reference), ooi_repository, scan_profile_repository, valid_time
    )


@pytest.fixture
def ipaddressv4(network, ooi_repository, scan_profile_repository, valid_time):
    return add_ooi(
        IPAddressV4(network=network.reference, address=IPv4Address("192.0.2.1")),
        ooi_repository,
        scan_profile_repository,
        valid_time,
    )


@pytest.fixture
def resolved_hostname(hostname, ipaddressv4, ooi_repository, scan_profile_repository, valid_time):
    return add_ooi(
        ResolvedHostname(hostname=hostname.reference, address=ipaddressv4.reference),
        ooi_repository,
        scan_profile_repository,
        valid_time,
    )


@pytest.fixture
def http_resource_http(hostname, ipaddressv4, network):
    ip_port = IPPort(address=ipaddressv4.reference, protocol="tcp", port=80)
    ip_service = IPService(ip_port=ip_port.reference, service=Service(name="http").reference)
    website = Website(ip_service=ip_service.reference, hostname=hostname.reference)
    web_url = HostnameHTTPURL(netloc=hostname.reference, path="/", scheme="http", network=network.reference, port=80)
    return HTTPResource(website=website.reference, web_url=web_url.reference)


@pytest.fixture
def http_resource_https(hostname, ipaddressv4, network):
    ip_port = IPPort(address=ipaddressv4.reference, protocol="tcp", port=443)
    ip_service = IPService(ip_port=ip_port.reference, service=Service(name="https").reference)
    website = Website(ip_service=ip_service.reference, hostname=hostname.reference)
    web_url = HostnameHTTPURL(netloc=hostname.reference, path="/", scheme="https", network=network.reference, port=443)
    return HTTPResource(website=website.reference, web_url=web_url.reference)


@pytest.fixture
def empty_scan_profile():
    return EmptyScanProfile(reference="test|reference")


@pytest.fixture
def declared_scan_profile():
    return DeclaredScanProfile(reference="test|reference", level=2)


@pytest.fixture
def app_settings():
    return Settings()


@pytest.fixture
def octopoes_service() -> OctopoesService:
    return OctopoesService(Mock(), Mock(), Mock(), Mock())


@pytest.fixture
def bit_runner(mocker) -> BitRunner:
    return mocker.patch("octopoes.core.service.BitRunner")


@pytest.fixture
def xtdb_http_client(request, app_settings: Settings) -> XTDBHTTPClient:
    test_node = f"test-{request.node.originalname}"
    client = get_xtdb_client(str(app_settings.xtdb_uri), test_node)

    return client


@pytest.fixture
def xtdb_session(xtdb_http_client: XTDBHTTPClient) -> Iterator[XTDBSession]:
    xtdb_http_client.create_node()

    yield XTDBSession(xtdb_http_client)
    xtdb_http_client.sync()
    xtdb_http_client.delete_node()


@pytest.fixture
def octopoes_api_connector(xtdb_session: XTDBSession) -> OctopoesAPIConnector:
    connector = OctopoesAPIConnector("http://ci_octopoes:80", xtdb_session.client.client)

    return connector


class MockEventManager:
    def __init__(self):
        self.queue = []
        self.processed = [0]
        self.client = "test"

    def publish(self, event) -> None:
        self.queue.append(event)

    def unprocessed(self) -> list:
        retval = self.queue[self.processed[-1] :]
        self.processed.append(len(self.queue))
        return retval

    def process_events(self, xtdb_octopoes_service: OctopoesService) -> int:
        targets = self.unprocessed()
        for event in targets:
            xtdb_octopoes_service.process_event(event)
        xtdb_octopoes_service.commit()
        return len(targets)

    def complete_process_events(self, xtdb_octopoes_service: OctopoesService, repeat: int = 3) -> int:
        retval = 0
        for _ in range(repeat):
            while True:
                val = self.process_events(xtdb_octopoes_service)
                if val == 0:
                    break
                retval += val
        return retval


@pytest.fixture
def event_manager(xtdb_session: XTDBSession) -> Mock:
    return MockEventManager()


@pytest.fixture
def xtdb_ooi_repository(xtdb_session: XTDBSession, event_manager) -> Iterator[XTDBOOIRepository]:
    yield XTDBOOIRepository(event_manager, xtdb_session)


@pytest.fixture
def xtdb_origin_repository(xtdb_session: XTDBSession, event_manager) -> Iterator[XTDBOOIRepository]:
    yield XTDBOriginRepository(event_manager, xtdb_session)


@pytest.fixture
def xtdb_origin_parameter_repository(xtdb_session: XTDBSession, event_manager) -> Iterator[XTDBOOIRepository]:
    yield XTDBOriginParameterRepository(event_manager, xtdb_session)


@pytest.fixture
def xtdb_scan_profile_repository(xtdb_session: XTDBSession, event_manager) -> Iterator[XTDBOOIRepository]:
    yield XTDBScanProfileRepository(event_manager, xtdb_session)


@pytest.fixture
def xtdb_octopoes_service(
    xtdb_ooi_repository: XTDBOOIRepository,
    xtdb_origin_repository: XTDBOriginRepository,
    xtdb_origin_parameter_repository: XTDBOriginParameterRepository,
    xtdb_scan_profile_repository: XTDBScanProfileRepository,
) -> OctopoesService:
    return OctopoesService(
        xtdb_ooi_repository, xtdb_origin_repository, xtdb_origin_parameter_repository, xtdb_scan_profile_repository
    )


@pytest.fixture
def mock_xtdb_session():
    return XTDBSession(Mock())


@pytest.fixture
def origin_repository(mock_xtdb_session):
    yield XTDBOriginRepository(Mock(spec=EventManager, client="test"), mock_xtdb_session)


def seed_system(xtdb_ooi_repository: XTDBOOIRepository, xtdb_origin_repository: XTDBOriginRepository, valid_time):
    network = Network(name="test")

    hostnames = [
        Hostname(network=network.reference, name="example.com"),
        Hostname(network=network.reference, name="a.example.com"),
        Hostname(network=network.reference, name="b.example.com"),
        Hostname(network=network.reference, name="c.example.com"),
        Hostname(network=network.reference, name="d.example.com"),
        Hostname(network=network.reference, name="e.example.com"),
        Hostname(network=network.reference, name="f.example.com"),
    ]

    addresses = [
        IPAddressV4(network=network.reference, address=ip_address("192.0.2.3")),
        IPAddressV6(network=network.reference, address=ip_address("3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230")),
    ]
    ports = [
        IPPort(address=addresses[0].reference, protocol="tcp", port=25),
        IPPort(address=addresses[0].reference, protocol="tcp", port=443),
        IPPort(address=addresses[0].reference, protocol="tcp", port=22),
        IPPort(address=addresses[1].reference, protocol="tcp", port=80),
    ]
    services = [Service(name="smtp"), Service(name="https"), Service(name="http"), Service(name="ssh")]
    ip_services = [
        IPService(ip_port=ports[0].reference, service=services[0].reference),
        IPService(ip_port=ports[1].reference, service=services[1].reference),
        IPService(ip_port=ports[2].reference, service=services[3].reference),
        IPService(ip_port=ports[3].reference, service=services[2].reference),
    ]

    resolved_hostnames = [
        ResolvedHostname(hostname=hostnames[0].reference, address=addresses[0].reference),  # ipv4
        ResolvedHostname(hostname=hostnames[0].reference, address=addresses[1].reference),  # ipv6
        ResolvedHostname(hostname=hostnames[1].reference, address=addresses[0].reference),
        ResolvedHostname(hostname=hostnames[2].reference, address=addresses[0].reference),
        ResolvedHostname(hostname=hostnames[3].reference, address=addresses[0].reference),
        ResolvedHostname(hostname=hostnames[4].reference, address=addresses[0].reference),
        ResolvedHostname(hostname=hostnames[5].reference, address=addresses[0].reference),
        ResolvedHostname(hostname=hostnames[3].reference, address=addresses[1].reference),
        ResolvedHostname(hostname=hostnames[4].reference, address=addresses[1].reference),
        ResolvedHostname(hostname=hostnames[6].reference, address=addresses[1].reference),
    ]
    certificates = [
        X509Certificate(
            subject="example.com",
            valid_from="2022-11-15T08:52:57",
            valid_until="2030-11-15T08:52:57",
            serial_number="abc123",
        )
    ]
    websites = [
        Website(ip_service=ip_services[0].reference, hostname=hostnames[0].reference, certificates=certificates[0]),
        Website(ip_service=ip_services[0].reference, hostname=hostnames[1].reference),
    ]
    software = [Software(name="DICOM")]
    instance = [SoftwareInstance(ooi=ports[0].reference, software=software[0].reference)]

    web_urls = [
        HostnameHTTPURL(netloc=hostnames[0].reference, path="/", scheme="http", network=network.reference, port=80),
        HostnameHTTPURL(netloc=hostnames[0].reference, path="/", scheme="https", network=network.reference, port=443),
    ]
    urls = [URL(network=network.reference, raw="https://test.com/security", web_url=web_urls[1].reference)]
    resources = [
        HTTPResource(website=websites[0].reference, web_url=web_urls[0].reference),
        HTTPResource(website=websites[0].reference, web_url=web_urls[1].reference),
    ]
    headers = [HTTPHeader(resource=resources[1].reference, key="test key", value="test value")]
    security_txts = [SecurityTXT(website=websites[1].reference, url=urls[0].reference, security_txt="test text")]
    finding_types = [
        KATFindingType(id="KAT-NO-CSP"),
        KATFindingType(id="KAT-CSP-VULNERABILITIES"),
        KATFindingType(id="KAT-NO-HTTPS-REDIRECT"),
        KATFindingType(id="KAT-NO-CERTIFICATE"),
        KATFindingType(id="KAT-CERTIFICATE-EXPIRED"),
        KATFindingType(id="KAT-CERTIFICATE-EXPIRING-SOON"),
    ]
    findings = [
        Finding(finding_type=finding_types[0].reference, ooi=resources[0].reference),
        Finding(finding_type=finding_types[2].reference, ooi=web_urls[0].reference),
        Finding(finding_type=finding_types[3].reference, ooi=websites[1].reference),
        Finding(finding_type=finding_types[4].reference, ooi=certificates[0].reference),
    ]

    oois = (
        hostnames
        + addresses
        + ports
        + services
        + ip_services
        + resolved_hostnames
        + websites
        + software
        + instance
        + web_urls
        + resources
        + headers
        + finding_types
        + findings
        + urls
        + security_txts
        + certificates
    )

    network_origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="kat_manual_csv",
        source=network.reference,
        source_method="manual",
        result=[network.reference],
        task_id=uuid.uuid4(),
    )
    xtdb_ooi_repository.save(network, valid_time=valid_time)
    xtdb_origin_repository.save(network_origin, valid_time=valid_time)

    origin = Origin(
        origin_type=OriginType.OBSERVATION,
        method="",
        source=network.reference,
        source_method="manual",
        result=[ooi.reference for ooi in oois],
        task_id=uuid.uuid4(),
    )

    for ooi in oois:
        xtdb_ooi_repository.save(ooi, valid_time=valid_time)

    xtdb_origin_repository.save(origin, valid_time=valid_time)

    xtdb_origin_repository.commit()
    xtdb_ooi_repository.commit()


def seed_report(
    name: str, valid_time, ooi_repository, origin_repository, input_reports: list[AssetReport] | None = None
) -> Report:
    recipe = ReportRecipe(
        report_type="concatenated-report",
        recipe_id=uuid.uuid4(),
        report_name_format="test",
        cron_expression="* * * *",
        input_recipe={},
        asset_report_types=[],
    )
    report = Report(
        name=name,
        date_generated=valid_time,
        organization_code="code",
        organization_name="name",
        organization_tags=["tag1", "tag2"],
        data_raw_id="raw",
        observed_at=valid_time,
        reference_date=valid_time,
        report_recipe=recipe.reference,
        input_oois=[input_report.reference for input_report in input_reports] if input_reports else [],
        report_type="concatenated-report",
    )
    report_origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="manual",
        source=report.reference,
        result=[report.reference],
        task_id=uuid.uuid4(),
    )
    recipe_origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="manual",
        source=recipe.reference,
        result=[recipe.reference],
        task_id=uuid.uuid4(),
    )

    ooi_repository.save(recipe, valid_time=valid_time)
    origin_repository.save(recipe_origin, valid_time=valid_time)

    ooi_repository.save(report, valid_time=valid_time)
    origin_repository.save(report_origin, valid_time=valid_time)

    origin_repository.commit()
    ooi_repository.commit()

    return report


def seed_asset_report(
    name: str, valid_time, ooi_repository, origin_repository, input_ooi: str = "testref"
) -> AssetReport:
    recipe = ReportRecipe(
        report_type="concatenated-report",
        recipe_id=uuid.uuid4(),
        report_name_format="test",
        cron_expression="* * * *",
        input_recipe={},
        asset_report_types=[],
    )

    asset_report = AssetReport(
        name=name,
        date_generated=valid_time,
        report_recipe=recipe.reference,
        organization_code="code",
        organization_name="name",
        organization_tags=["tag1", "tag2"],
        data_raw_id="raw",
        reference_date=valid_time,
        observed_at=valid_time,
        input_ooi=input_ooi,
        report_type="system-report",
    )
    report_origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="manual",
        source=asset_report.reference,
        result=[asset_report.reference],
        task_id=uuid.uuid4(),
    )
    recipe_origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="manual",
        source=recipe.reference,
        result=[recipe.reference],
        task_id=uuid.uuid4(),
    )

    ooi_repository.save(recipe, valid_time=valid_time)
    origin_repository.save(recipe_origin, valid_time=valid_time)

    ooi_repository.save(asset_report, valid_time=valid_time)
    origin_repository.save(report_origin, valid_time=valid_time)

    origin_repository.commit()
    ooi_repository.commit()

    return asset_report
