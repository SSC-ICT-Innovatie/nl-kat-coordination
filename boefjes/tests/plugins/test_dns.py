import uuid
from ipaddress import IPv4Address, IPv6Address

import pytest
from pydantic import BaseModel

from boefjes.worker.job_models import (
    Boefje,
    BoefjeMeta,
    Normalizer,
    NormalizerMeta,
    ObservationsWithoutInputOOI,
    RawDataMeta,
)
from octopoes.models import Reference
from octopoes.models.ooi.dns.records import (
    DNSAAAARecord,
    DNSARecord,
    DNSCNAMERecord,
    DNSMXRecord,
    DNSNSRecord,
    DNSSOARecord,
    DNSTXTRecord,
)
from octopoes.models.ooi.dns.zone import DNSZone, Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, Network
from tests.loading import get_dummy_data


def test_dns_normalizer(normalizer_runner):
    internet = Network(name="internet")

    zone_hostname = Hostname(name="example.nl", network=internet.reference)
    zone = DNSZone(hostname=zone_hostname.reference)
    zone_hostname.dns_zone = zone.reference

    ip_v4_addresses = [
        IPAddressV4(network=internet.reference, address=IPv4Address("94.198.159.35")),
        IPAddressV4(network=internet.reference, address=IPv4Address("94.198.159.36")),
    ]
    dns_a_records = [
        DNSARecord(hostname=zone_hostname.reference, value=str(ip.address), address=ip.reference, ttl=14364)
        for ip in ip_v4_addresses
    ]
    ip_v6_addresses = [
        IPAddressV6(network=internet.reference, address=IPv6Address("2a00:d78:0:712:94:198:159:35")),
        IPAddressV6(network=internet.reference, address=IPv6Address("2a00:d78:0:712:94:198:159:36")),
    ]
    dns_aaaa_records = [
        DNSAAAARecord(hostname=zone_hostname.reference, value=str(ip.address), address=ip.reference, ttl=14400)
        for ip in ip_v6_addresses
    ]
    dns_txt_records = [
        DNSTXTRecord(hostname=zone_hostname.reference, value="v=spf1 redirect=spf-a.example.nl", ttl=14400)
    ]

    mx_hostnames = [
        Hostname(network=internet.reference, name="mail.example.nl"),
        Hostname(network=internet.reference, name="mail2.example.nl"),
    ]
    dns_mx_records = [
        DNSMXRecord(
            hostname=zone_hostname.reference,
            value=f"10 {mx_rec.name}.",
            ttl=14400,
            mail_hostname=mx_rec.reference,
            preference=10,
        )
        for mx_rec in mx_hostnames
    ]

    ns_hostnames = [
        Hostname(name=value, network=internet.reference)
        for value in ["ns3.examplenl.org", "ns1.examplenl.nl", "ns2.examplenl.eu", "ns0.examplenl.com"]
    ]

    ns_records = [
        DNSNSRecord(
            hostname=zone_hostname.reference,
            value=ns_hostname.name + ".",
            name_server_hostname=ns_hostname.reference,
            ttl=2634,
        )
        for ns_hostname in ns_hostnames
    ]

    soa_hostname = Hostname(network=internet.reference, name="ns1.examplenl.nl", dns_zone=zone.reference)
    soa_record = DNSSOARecord(
        hostname=zone_hostname.reference,
        value="ns1.examplenl.nl. hostmaster.sidn.nl. 2021111101 14400 7200 1209600 86400",
        soa_hostname=soa_hostname.reference,
        ttl=14340,
        serial=2021111101,
        retry=7200,
        refresh=14400,
        expire=1209600,
        minimum=86400,
    )

    # noinspection PyTypeChecker
    expected = (
        [zone_hostname, zone]
        + ip_v4_addresses
        + dns_a_records
        + ip_v6_addresses
        + dns_aaaa_records
        + dns_txt_records
        + mx_hostnames
        + dns_mx_records
        + ns_hostnames
        + ns_records
        + [soa_record]
    )

    meta = NormalizerMeta.model_validate_json(get_dummy_data("dns-normalize.json"))
    results = normalizer_runner.run(meta, get_dummy_data("inputs/dns-result-example.nl.json"))

    assert len(results.observations) == 1
    assert len(list(map(BaseModel.model_dump, expected))) == len(
        list(map(BaseModel.model_dump, results.observations[0].results))
    )


def test_dns_normalizer_cname(normalizer_runner):
    internet = Network(name="internet")

    zone_hostname = Hostname(network=internet.reference, name="example.nl")
    zone = DNSZone(hostname=zone_hostname.reference)
    zone_hostname.dns_zone = zone.reference

    input_hostname = Hostname(network=internet.reference, name="www.example.nl", dns_zone=zone.reference)
    cname_target = Hostname(network=internet.reference, name="webredir.examplenl.nl")

    soa_hostname = Hostname(network=internet.reference, name="ns1.examplenl.nl")
    soa_record = DNSSOARecord(
        hostname=zone_hostname.reference,
        value="ns1.examplenl.nl. hostmaster.sidn.nl. 2021111101 14400 7200 1209600 86400",
        ttl=14340,
        soa_hostname=soa_hostname.reference,
        serial=2021111101,
        refresh=14400,
        retry=7200,
        expire=1209600,
        minimum=86400,
    )

    cname_record = DNSCNAMERecord(
        hostname=input_hostname.reference,
        value=cname_target.name + ".",
        ttl=10800,
        target_hostname=cname_target.reference,
    )

    ip_address = IPAddressV4(network=internet.reference, address=IPv4Address("94.198.159.35"))
    dns_a_record = DNSARecord(
        hostname=cname_target.reference, address=ip_address.reference, value=str(ip_address.address), ttl=10800
    )

    expected = [
        zone,
        zone_hostname,
        soa_hostname,
        soa_record,
        cname_target,
        cname_record,
        ip_address,
        dns_a_record,
        input_hostname,
    ]

    meta = NormalizerMeta(
        id=uuid.UUID("72c7d302-0d6f-407a-aaec-9ffcad0ee7c6"),
        normalizer=Normalizer(id="kat_dns_normalize"),
        raw_data=RawDataMeta(
            id=uuid.UUID("3b8397ba-50e4-476e-834a-2fa2595a43a5"),
            boefje_meta=BoefjeMeta(
                id=uuid.UUID("10535bba-2715-42f9-be47-ccd985b59eea"),
                boefje=Boefje(id="dns-records"),
                organization="_dev",
                input_ooi="Hostname|internet|www.example.nl",
                arguments={"domain": "www.example.nl.", "input": {"name": "www.example.nl."}},
            ),
            mime_types=[{"value": "boefje/dns-records"}],
        ),
    )

    results = normalizer_runner.run(meta, get_dummy_data("inputs/dns-result-www.example.nl.json"))
    assert len(list(map(BaseModel.model_dump, expected))) == len(
        list(map(BaseModel.model_dump, results.observations[0].results))
    )


def test_parse_record_null_mx_record(normalizer_runner):
    meta = NormalizerMeta(
        id=uuid.UUID("d7d65462-5ced-4a57-a1d7-c6d2edf38354"),
        normalizer=Normalizer(id="kat_dns_normalize"),
        raw_data=RawDataMeta(
            id=uuid.UUID("94fe3b47-fb41-4ad7-b2de-1bfe63460c98"),
            boefje_meta=BoefjeMeta(
                id=uuid.UUID("f1e72e47-c11f-47e9-953a-52e3b6833eaf"),
                boefje=Boefje(id="dns-records"),
                organization="_dev",
                input_ooi="Hostname|internet|english.example.nl",
                arguments={"domain": "english.example.nl", "input": {"name": "english.example.nl"}},
            ),
            mime_types=[{"value": "boefje/dns-records"}],
        ),
    )

    answer = get_dummy_data("inputs/dns-result-mx-example.nl.json")

    internet = Network(name="internet")
    input_hostname = Hostname(network=internet.reference, name="english.example.nl")

    cname_target = Hostname(network=internet.reference, name="redir.example.nl")
    cname_record = DNSCNAMERecord(
        hostname=input_hostname.reference, value="redir.example.nl.", ttl=60, target_hostname=cname_target.reference
    )
    mx_record = DNSMXRecord(hostname=cname_target.reference, value="0 .", ttl=14400, preference=0)

    results = normalizer_runner.run(meta, answer)

    expected = [cname_target, cname_record, mx_record, input_hostname]
    assert len(list(map(BaseModel.model_dump, expected))) == len(
        list(map(BaseModel.model_dump, results.observations[0].results))
    )


def test_parse_cname_soa(normalizer_runner):
    internet = Network(name="internet")

    zone_hostname = Hostname(network=internet.reference, name="example.com")
    zone = DNSZone(hostname=zone_hostname.reference)
    zone_hostname.dns_zone = zone.reference

    input_hostname = Hostname(network=internet.reference, name="www.example.com", dns_zone=zone.reference)

    cname_record = DNSCNAMERecord(
        hostname=input_hostname.reference, value="example.com.", ttl=60, target_hostname=zone_hostname.reference
    )
    ip_address = IPAddressV4(network=internet.reference, address=IPv4Address("94.198.159.35"))
    a_record = DNSARecord(
        hostname=zone_hostname.reference, address=ip_address.reference, value=str(ip_address.address), ttl=60
    )
    soa_hostname = Hostname(network=internet.reference, name="ns.icann.org")
    ns_hostnames = [
        Hostname(name=value, network=internet.reference) for value in ["a.iana-servers.net", "b.iana-servers.net"]
    ]
    ns_records = [
        DNSNSRecord(
            hostname=zone_hostname.reference,
            value=ns_hostname.name + ".",
            name_server_hostname=ns_hostname.reference,
            ttl=60,
        )
        for ns_hostname in ns_hostnames
    ]
    soa_record = DNSSOARecord(
        hostname=zone_hostname.reference,
        value="ns.icann.org. noc.dns.icann.org. 2022040432 7200 3600 1209600 3600",
        ttl=21,
        soa_hostname=soa_hostname.reference,
        serial=2022040432,
        retry=3600,
        refresh=7200,
        expire=1209600,
        minimum=3600,
    )
    txt_record = DNSTXTRecord(hostname=zone_hostname.reference, value="v=spf1 -all", ttl=60)
    mx_record = DNSMXRecord(
        hostname=zone_hostname.reference,
        value="0 example.com.",
        ttl=60,
        mail_hostname=zone_hostname.reference,
        preference=0,
    )

    meta = NormalizerMeta(
        id=uuid.UUID("a2a85d54-a6ce-495d-b7a5-23c1a79f4cec"),
        normalizer=Normalizer(id="kat_dns_normalize"),
        raw_data=RawDataMeta(
            id=uuid.UUID("ac481bc2-a524-4dcc-91a4-28ed9c2c142b"),
            boefje_meta=BoefjeMeta(
                id=uuid.UUID("0671b9ac-1624-4c09-a94a-4f9edbc40064"),
                boefje=Boefje(id="dns-records"),
                organization="_dev",
                input_ooi="Hostname|internet|www.example.com",
                arguments={"domain": "www.example.com", "input": {"name": "www.example.com"}},
            ),
            mime_types=[{"value": "boefje/dns-records"}],
        ),
    )

    results = normalizer_runner.run(meta, get_dummy_data("inputs/dns-result-example.com-cnames.json"))

    expected = (
        [
            zone,
            zone_hostname,
            cname_record,
            ip_address,
            a_record,
            soa_record,
            txt_record,
            mx_record,
            input_hostname,
            soa_hostname,
        ]
        + ns_hostnames
        + ns_records
    )
    assert len(list(map(BaseModel.model_dump, expected))) == len(
        list(map(BaseModel.model_dump, results.observations[0].results))
    )


def test_find_parent_dns_zone(normalizer_runner):
    internet = Network(name="internet")

    requested_zone = DNSZone(hostname=Hostname(network=internet.reference, name="sub.example.nl").reference)
    parent_zone_hostname = Hostname(network=internet.reference, name="example.nl")
    parent_zone = DNSZone(hostname=parent_zone_hostname.reference)
    parent_zone_hostname.dns_zone = parent_zone.reference

    requested_zone.parent = parent_zone.reference

    name_server_hostname = Hostname(network=internet.reference, name="ns1.examplenl.nl")

    soa_record = DNSSOARecord(
        hostname=parent_zone_hostname.reference,
        value="ns1.examplenl.nl. hostmaster.sidn.nl. 2021111101 14400 7200 1209600 86400",
        ttl=14340,
        soa_hostname=name_server_hostname.reference,
        serial=2021111101,
        retry=7200,
        refresh=14400,
        expire=1209600,
        minimum=86400,
    )

    input_ = DNSZone(
        hostname=Hostname(network=Reference.from_str("Network|internet"), name="sub.example.nl").reference
    ).serialize()

    meta = NormalizerMeta(
        id=uuid.UUID("ee8374bb-e79f-4083-9ce9-add4f96006f2"),
        normalizer=Normalizer(id="kat_dns_zone_normalize"),
        raw_data=RawDataMeta(
            id=uuid.UUID("2147da2a-921c-4c51-aef3-fa82d8d6e089"),
            boefje_meta=BoefjeMeta(
                id=uuid.UUID("ff1f0d62-a2e0-480f-8b11-5fb24974edce"),
                boefje=Boefje(id="dns-records"),
                organization="_dev",
                input_ooi="DnsZone|internet|sub.example.nl",
                arguments={"input": input_},
            ),
            mime_types=[{"value": "boefje/dns-records"}],
        ),
    )

    results = normalizer_runner.run(meta, get_dummy_data("inputs/dns-zone-result-sub.example.nl.txt"))

    expected = [requested_zone, parent_zone, parent_zone_hostname, name_server_hostname, soa_record]
    assert len(list(map(BaseModel.model_dump, expected))) == len(
        list(map(BaseModel.model_dump, results.observations[0].results))
    )


def test_exception_raised_no_input_ooi(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("dns-normalize.json"))
    meta.raw_data.boefje_meta.input_ooi = None

    with pytest.raises(ObservationsWithoutInputOOI):
        normalizer_runner.run(meta, get_dummy_data("inputs/dns-result-example.nl.json"))
