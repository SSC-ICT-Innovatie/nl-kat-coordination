from octopoes.models import DeclaredScanProfile


def test_recalculate_no_profiles(valid_time, ooi_repository, scan_profile_repository, octopoes_service):
    octopoes = octopoes_service
    octopoes.ooi_repository = ooi_repository
    octopoes.scan_profile_repository = scan_profile_repository
    octopoes.recalculate_scan_profiles(valid_time)


def test_recalculate_only_empty_profiles(
    valid_time, ooi_repository, scan_profile_repository, octopoes_service, resolved_hostname
):
    octopoes = octopoes_service
    octopoes.ooi_repository = ooi_repository
    octopoes.scan_profile_repository = scan_profile_repository
    octopoes.recalculate_scan_profiles(valid_time)


def test_recalculate_inherent(
    valid_time,
    dns_zone,
    hostname,
    resolved_hostname,
    ipaddressv4,
    octopoes_service,
    ooi_repository,
    scan_profile_repository,
):
    octopoes = octopoes_service
    octopoes.ooi_repository = ooi_repository
    octopoes.scan_profile_repository = scan_profile_repository
    octopoes.scan_profile_repository.save(None, DeclaredScanProfile(reference=hostname.reference, level=4), valid_time)

    octopoes.recalculate_scan_profiles(valid_time)

    assert octopoes.scan_profile_repository.get(ipaddressv4.reference, valid_time).level == 4
    assert octopoes.scan_profile_repository.get(resolved_hostname.reference, valid_time).level == 4
    assert octopoes.scan_profile_repository.get(dns_zone.reference, valid_time).level == 1


def test_recalculate_inherent_max(
    valid_time, dns_zone, resolved_hostname, ipaddressv4, octopoes_service, ooi_repository, scan_profile_repository
):
    octopoes = octopoes_service
    octopoes.ooi_repository = ooi_repository
    octopoes.scan_profile_repository = scan_profile_repository
    octopoes.scan_profile_repository.save(None, DeclaredScanProfile(reference=dns_zone.reference, level=4), valid_time)

    octopoes.recalculate_scan_profiles(valid_time)

    assert octopoes.scan_profile_repository.get(resolved_hostname.reference, valid_time).level == 2
    assert octopoes.scan_profile_repository.get(ipaddressv4.reference, valid_time).level == 2
    assert octopoes.scan_profile_repository.get(resolved_hostname.reference, valid_time).level == 2


def test_recalculate_inherent_recalculate(
    valid_time,
    dns_zone,
    hostname,
    resolved_hostname,
    ipaddressv4,
    octopoes_service,
    ooi_repository,
    scan_profile_repository,
):
    octopoes = octopoes_service
    octopoes.ooi_repository = ooi_repository
    octopoes.scan_profile_repository = scan_profile_repository
    octopoes.scan_profile_repository.save(None, DeclaredScanProfile(reference=hostname.reference, level=3), valid_time)

    octopoes.recalculate_scan_profiles(valid_time)

    assert octopoes.scan_profile_repository.get(ipaddressv4.reference, valid_time).level == 3
    assert octopoes.scan_profile_repository.get(resolved_hostname.reference, valid_time).level == 3
    assert octopoes.scan_profile_repository.get(dns_zone.reference, valid_time).level == 1

    octopoes.recalculate_scan_profiles(valid_time)

    assert octopoes.scan_profile_repository.get(ipaddressv4.reference, valid_time).level == 3
    assert octopoes.scan_profile_repository.get(resolved_hostname.reference, valid_time).level == 3
    assert octopoes.scan_profile_repository.get(dns_zone.reference, valid_time).level == 1

    profile = DeclaredScanProfile(reference=hostname.reference, level=2)
    octopoes.scan_profile_repository.save(None, profile, valid_time)

    octopoes.recalculate_scan_profiles(valid_time)

    assert octopoes.scan_profile_repository.get(ipaddressv4.reference, valid_time).level == 2
    assert octopoes.scan_profile_repository.get(resolved_hostname.reference, valid_time).level == 2
    assert octopoes.scan_profile_repository.get(dns_zone.reference, valid_time).level == 1

    octopoes.scan_profile_repository.delete(profile, valid_time)

    octopoes.recalculate_scan_profiles(valid_time)

    assert octopoes.scan_profile_repository.get(ipaddressv4.reference, valid_time).level == 0
    assert octopoes.scan_profile_repository.get(resolved_hostname.reference, valid_time).level == 0
    assert octopoes.scan_profile_repository.get(dns_zone.reference, valid_time).level == 0
