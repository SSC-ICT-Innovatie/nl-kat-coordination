import os
from datetime import datetime

import pytest

from octopoes.models import DeclaredScanProfile, ScanLevel
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.findings import Finding, KATFindingType, MutedFinding, RiskLevelSeverity
from octopoes.models.ooi.network import IPAddressV4, Network
from octopoes.models.pagination import Paginated
from octopoes.models.path import Path
from octopoes.repositories.ooi_repository import XTDBOOIRepository
from octopoes.repositories.scan_profile_repository import XTDBScanProfileRepository
from octopoes.xtdb.query import Aliased, Query

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)


def test_list_oois(xtdb_ooi_repository: XTDBOOIRepository, valid_time: datetime):
    xtdb_ooi_repository.save(Network(name="test"), valid_time)

    assert xtdb_ooi_repository.list_oois({Network}, valid_time) == Paginated(count=0, items=[])

    xtdb_ooi_repository.session.commit()

    # list() does not return any OOI without a scan profile
    assert xtdb_ooi_repository.list_oois({Network}, valid_time) == Paginated(count=0, items=[])


def test_load_bulk(
    xtdb_ooi_repository: XTDBOOIRepository,
    xtdb_scan_profile_repository: XTDBScanProfileRepository,
    valid_time: datetime,
):
    network = Network(name="test")
    xtdb_ooi_repository.save(network, valid_time)

    network2 = Network(name="test2")
    xtdb_ooi_repository.save(network2, valid_time)

    network3 = Network(name="test3")
    xtdb_ooi_repository.save(network3, valid_time)

    xtdb_ooi_repository.session.commit()

    xtdb_scan_profile_repository.save(
        None, DeclaredScanProfile(reference=network.reference, level=ScanLevel.L2), valid_time
    )
    xtdb_scan_profile_repository.save(
        None, DeclaredScanProfile(reference=network2.reference, level=ScanLevel.L2), valid_time
    )
    xtdb_scan_profile_repository.save(
        None, DeclaredScanProfile(reference=network3.reference, level=ScanLevel.L2), valid_time
    )
    xtdb_scan_profile_repository.commit()

    networks = xtdb_ooi_repository.load_bulk(
        {network.reference, network2.reference, network3.reference}, valid_time, include_scan_levels=False
    )
    assert [ooi.reference for ooi in networks.values()] == [network.reference, network2.reference, network3.reference]

    assert networks[network.reference].scan_profile is None
    assert networks[network2.reference].scan_profile is None
    assert networks[network3.reference].scan_profile is None

    networks = xtdb_ooi_repository.load_bulk(
        {network.reference, network2.reference, network3.reference}, valid_time, include_scan_levels=True
    )
    assert [ooi.reference for ooi in networks.values()] == [network.reference, network2.reference, network3.reference]

    assert networks[network.reference].scan_profile is not None
    assert networks[network2.reference].scan_profile is not None
    assert networks[network3.reference].scan_profile is not None


def test_get_tree_search_types_returns_descendant_findings(
    xtdb_ooi_repository: XTDBOOIRepository, valid_time: datetime
):
    """Regression test for #5202: get_tree(search_types={Finding}) must return findings attached to
    descendant OOIs, not only findings directly on the root. #5088 pruned the traversal by the leaf
    type, which destroyed the path to deep findings (e.g. a CVE on an HTTPHeader several hops down)."""
    network = Network(name="test")
    hostname = Hostname(network=network.reference, name="example.com")
    address = IPAddressV4(network=network.reference, address="192.0.2.1")
    # Hostname <- ResolvedHostname -> IPAddressV4, so the address is two hops from the hostname.
    resolved = ResolvedHostname(hostname=hostname.reference, address=address.reference)
    finding_type = KATFindingType(id="KAT-DEEP-FINDING")
    # A finding three hops down from the hostname (Hostname <- ResolvedHostname -> IPAddressV4 <- Finding)
    deep_finding = Finding(ooi=address.reference, finding_type=finding_type.reference)
    # And a finding directly on the hostname, to confirm direct findings still come through.
    direct_finding = Finding(ooi=hostname.reference, finding_type=finding_type.reference)

    for ooi in [network, hostname, address, resolved, finding_type, deep_finding, direct_finding]:
        xtdb_ooi_repository.save(ooi, valid_time)
    xtdb_ooi_repository.session.commit()

    tree = xtdb_ooi_repository.get_tree(hostname.reference, valid_time, search_types={Finding}, depth=5)

    finding_references = {ref for ref, ooi in tree.store.items() if ooi.ooi_type == "Finding"}
    assert str(direct_finding.reference) in finding_references
    assert str(deep_finding.reference) in finding_references


def test_complex_query(xtdb_ooi_repository: XTDBOOIRepository, valid_time: datetime):
    network = Network(name="testnetwork")
    network2 = Network(name="testnetwork2")
    xtdb_ooi_repository.save(network, valid_time)
    xtdb_ooi_repository.save(network2, valid_time)
    xtdb_ooi_repository.save(Hostname(network=network2.reference, name="testhostname"), valid_time)
    xtdb_ooi_repository.session.commit()

    # router logic
    object_path = Path.parse("Network.<network[is Hostname]")
    sources = ["Network|testnetwork", "Network|testnetwork2"]
    source_pk_alias = Aliased(object_path.segments[0].source_type, field="primary_key")
    query = (
        Query.from_path(object_path)
        .find(source_pk_alias)
        .pull(Network)
        .where(Network, primary_key=source_pk_alias)
        .where_in(Network, primary_key=sources)
    )

    result = xtdb_ooi_repository.query(query, valid_time)

    assert len(result) == 1


def test_kat_finding_type_metadata_persists_on_partial_save(
    xtdb_ooi_repository: XTDBOOIRepository, valid_time: datetime
):
    """Classification must persist through XTDB and remain intentionally editable."""
    stored = KATFindingType(
        id="KAT-CLASSIFICATION-PERSISTENCE", groups=["web-security", "http-security-headers"], tags=["misconfiguration"]
    )
    xtdb_ooi_repository.save(stored, valid_time)
    xtdb_ooi_repository.session.commit()

    xtdb_ooi_repository.save(KATFindingType(id=stored.id), valid_time)
    xtdb_ooi_repository.session.commit()

    hydrated = xtdb_ooi_repository.get(stored.reference, valid_time)
    assert hydrated.groups == stored.groups
    assert hydrated.tags == stored.tags

    xtdb_ooi_repository.save(KATFindingType(id=stored.id, groups=[], tags=[]), valid_time)
    xtdb_ooi_repository.session.commit()

    cleared = xtdb_ooi_repository.get(stored.reference, valid_time)
    assert cleared.groups == []
    assert cleared.tags == []


def test_kat_finding_type_backfill_existing_xtdb_ooi(xtdb_ooi_repository: XTDBOOIRepository, valid_time: datetime):
    """An older OOI lacking attributes receives groups and tags after rehydration."""
    legacy = KATFindingType(id="KAT-CLASSIFICATION-BACKFILL", name="Legacy finding type")
    xtdb_ooi_repository.save(legacy, valid_time)
    xtdb_ooi_repository.session.commit()

    refreshed = KATFindingType(
        id=legacy.id, groups=["web-security", "http-security-headers"], tags=["misconfiguration"]
    )
    xtdb_ooi_repository.save(refreshed, valid_time)
    xtdb_ooi_repository.session.commit()

    stored = xtdb_ooi_repository.get(legacy.reference, valid_time)
    assert stored.name == legacy.name
    assert stored.groups == refreshed.groups
    assert stored.tags == refreshed.tags


def test_findings_group_and_tag_filters_before_pagination(xtdb_ooi_repository: XTDBOOIRepository, valid_time: datetime):
    """XTDB matches individual array elements in both paginated and count queries."""
    network = Network(name="finding-filter-test")
    xtdb_ooi_repository.save(network, valid_time)
    cases = [
        ("WEB-BOTH-LOW", ["web-security", "http-security-headers"], ["misconfiguration"], 4.0),
        ("WEB-ONLY", ["web-security"], [], 5.0),
        ("DNS-BOTH", ["dns-security"], ["misconfiguration"], 6.0),
        ("WEB-BOTH-HIGH", ["web-security"], ["misconfiguration"], 8.0),
        ("UNCLASSIFIED", [], [], 9.0),
    ]
    created = {}
    for i, (identifier, groups, tags, score) in enumerate(cases):
        hostname = Hostname(network=network.reference, name=f"filter{i}.example")
        finding_type = KATFindingType(
            id=f"KAT-{identifier}", groups=groups, tags=tags, risk_score=score, risk_severity=RiskLevelSeverity.HIGH
        )
        finding = Finding(ooi=hostname.reference, finding_type=finding_type.reference)
        for ooi in (hostname, finding_type, finding):
            xtdb_ooi_repository.save(ooi, valid_time)
        created[identifier] = finding
    xtdb_ooi_repository.session.commit()

    severities = {RiskLevelSeverity.HIGH}

    def query(**kwargs):
        return xtdb_ooi_repository.list_findings(severities, valid_time, **kwargs)

    assert query(limit=0).count == 5
    assert query(group="web-security", limit=0).count == 3
    assert query(tag="misconfiguration", limit=0).count == 3
    assert query(group="web-security", tag="misconfiguration", limit=0).count == 2
    assert query(group="tls-certificates", limit=0).count == 0
    assert query(group="web-security", tag="misconfiguration", limit=1).items == [created["WEB-BOTH-HIGH"]]
    second_page = query(group="web-security", tag="misconfiguration", offset=1, limit=1)
    assert second_page.count == 2
    assert second_page.items == [created["WEB-BOTH-LOW"]]
    empty_page = query(group="web-security", tag="misconfiguration", offset=3, limit=1)
    assert empty_page.count == 2
    assert empty_page.items == []
    assert query(group="web-security", tag="misconfiguration", search_string="filter0", limit=0).count == 1
    assert (
        xtdb_ooi_repository.list_findings(
            set(), valid_time, group="web-security", tag="misconfiguration", limit=0
        ).count
        == 0
    )

    xtdb_ooi_repository.save(MutedFinding(finding=created["WEB-BOTH-HIGH"].reference), valid_time)
    xtdb_ooi_repository.session.commit()
    assert query(group="web-security", tag="misconfiguration", exclude_muted=True, limit=0).count == 1
    assert query(group="web-security", tag="misconfiguration", only_muted=True, limit=0).count == 1
