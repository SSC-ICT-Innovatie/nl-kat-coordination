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


def test_scan_profile_inheritance_no_path_going_down(
    octopoes_service,
    ooi_repository,
    scan_profile_repository,
    valid_time,
    dns_zone,
    hostname,
    ipaddressv4,
    resolved_hostname,
):
    # Reproduces issue #5283: a ResolvedHostname at L2 has two outgoing edges:
    #   - hostname  -> Hostname (max_inherit=4) — the real inheritance path
    #   - address   -> IPAddress (max_inherit=0) — cannot transfer any level
    # Declare L2 on both DNSZone (so Hostname inherits L2) and IPAddressV4.
    # The old code did not pre-filter the address path and would pick the
    # IPAddress (DECLARED, but inherited_level=0) via the declared shortcut,
    # producing a chain that goes L2 -> L0 — "down" instead of "up".
    # The fix pre-filters paths by path_can_inherit_level(required_level),
    # so the address edge (max_inherit=0 < 2) is never considered.
    octopoes = octopoes_service
    octopoes.ooi_repository = ooi_repository
    octopoes.scan_profile_repository = scan_profile_repository
    octopoes.scan_profile_repository.save(None, DeclaredScanProfile(reference=dns_zone.reference, level=2), valid_time)
    octopoes.scan_profile_repository.save(
        None, DeclaredScanProfile(reference=ipaddressv4.reference, level=2), valid_time
    )

    octopoes.recalculate_scan_profiles(valid_time)
    ooi = octopoes.get_ooi(resolved_hostname.reference, valid_time)
    assert ooi.scan_profile.level == 2  # ResolvedHostname inherits L2

    start_section = InheritanceSection(
        reference=ooi.reference,
        level=ooi.scan_profile.level,
        inherited_level=None,
        scan_profile_type=ooi.scan_profile.scan_profile_type,
    )

    chain = octopoes_service.get_scan_profile_inheritance(resolved_hostname.reference, valid_time, [start_section])

    # The chain must reach a DECLARED source without going through the IPAddress
    # (whose edge has max_inherit=0 and would show up as L0 in the old code).
    assert chain[-1].scan_profile_type == ScanProfileType.DECLARED
    assert chain[-1].reference == dns_zone.reference  # the actual declared source
    assert len(chain) == 3  # ResolvedHostname -> Hostname -> DNSZone
    # Levels never go down — the original "path going down" bug
    assert [s.level for s in chain] == sorted(s.level for s in chain)
