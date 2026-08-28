import os
from datetime import datetime
from math import isclose
from unittest.mock import Mock

import pytest
from nibbles.default_findingtype_risk.nibble import NIBBLE as default_findingtype_risk_nibble
from nibbles.missing_spf.nibble import NIBBLE as missing_spf_nibble
from nibbles.runner import NibblesRunner

from octopoes.core.service import OctopoesService
from octopoes.models import ScanLevel
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import Network

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

STATIC_IP = ".".join((4 * "1 ").split())


def test_default_findingtype_risk_simple(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {default_findingtype_risk_nibble.id: default_findingtype_risk_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    finding_type = KATFindingType(id="KAT-DUMMY-FINDING")
    xtdb_octopoes_service.ooi_repository.save(finding_type, valid_time)

    finding = Finding(ooi=hostname.reference, finding_type=finding_type.reference)
    xtdb_octopoes_service.ooi_repository.save(finding, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get(finding_type.reference, valid_time)

    assert xtdb_finding_type.risk_score is None

    nibbler.infer([xtdb_finding_type], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get("KATFindingType|KAT-DUMMY-FINDING", valid_time)
    assert isclose(xtdb_finding_type.risk_score, 0.0)


def test_default_findingtype_risk_should_not_go_back_to_pending(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {
        default_findingtype_risk_nibble.id: default_findingtype_risk_nibble,
        missing_spf_nibble.id: missing_spf_nibble,
    }
    nibbler.nibbles[missing_spf_nibble.id].signature[0].min_scan_level = ScanLevel.L0

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_hostname = xtdb_octopoes_service.ooi_repository.get(hostname.reference, valid_time)

    nibbler.infer([xtdb_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get("KATFindingType|KAT-NO-SPF", valid_time)
    assert xtdb_finding_type.risk_score is None

    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get("KATFindingType|KAT-NO-SPF", valid_time)
    nibbler.infer([xtdb_finding_type], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get("KATFindingType|KAT-NO-SPF", valid_time)
    assert isclose(xtdb_finding_type.risk_score, 0.0)

    # default risk score should be given by default_findingtype_risk_nibble

    # simulate a change in the risk score by a boefje
    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get("KATFindingType|KAT-NO-SPF", valid_time)
    xtdb_finding_type.risk_score = 5.0
    xtdb_octopoes_service.ooi_repository.save(xtdb_finding_type, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    # check that save is successful
    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get("KATFindingType|KAT-NO-SPF", valid_time)
    assert isclose(xtdb_finding_type.risk_score, 5.0)

    # another hostname is made with same finding type
    hostname2 = Hostname(name="example2.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname2, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_hostname2 = xtdb_octopoes_service.ooi_repository.get(hostname2.reference, valid_time)

    nibbler.infer([xtdb_hostname2], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get("KATFindingType|KAT-NO-SPF", valid_time)
    nibbler.infer([xtdb_finding_type], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    # make sure that the risk score is not reset to 0
    xtdb_finding_type = xtdb_octopoes_service.ooi_repository.get("KATFindingType|KAT-NO-SPF", valid_time)
    assert isclose(xtdb_finding_type.risk_score, 5.0)
