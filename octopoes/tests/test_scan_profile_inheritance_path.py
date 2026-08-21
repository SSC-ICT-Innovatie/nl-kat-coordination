from octopoes.models import DeclaredScanProfile, ScanProfileType
from octopoes.models.explanation import InheritanceSection


def test_scan_profile_inheritance_duplicate_neighbour_paths(
    octopoes_service, ooi_repository, scan_profile_repository, valid_time, dns_zone, hostname
):
    # Declare L4 on the hostname; the zone apex reaches the same neighbour via two
    # inheritable paths (hostname <- DNSZone)
    octopoes = octopoes_service
    octopoes.ooi_repository = ooi_repository
    octopoes.scan_profile_repository = scan_profile_repository
    octopoes.scan_profile_repository.save(None, DeclaredScanProfile(reference=hostname.reference, level=4), valid_time)

    octopoes.recalculate_scan_profiles(valid_time)
    ooi = octopoes.get_ooi(dns_zone.reference, valid_time)
    start_section = InheritanceSection(
        reference=ooi.reference,
        level=ooi.scan_profile.level,
        inherited_level=None,
        scan_profile_type=ooi.scan_profile.scan_profile_type,
    )

    chain = octopoes_service.get_scan_profile_inheritance(dns_zone.reference, valid_time, [start_section])

    assert chain[-1].scan_profile_type == ScanProfileType.DECLARED  # resolves, no ValueError
    # highest-edge-wins (the reversed() bug): levels toward the source are non-decreasing
    assert [s.level for s in chain] == sorted(s.level for s in chain)
