import os
from datetime import datetime

import pytest

from octopoes.models import DeclaredScanProfile, ScanLevel
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
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
