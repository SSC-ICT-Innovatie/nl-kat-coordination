import uuid
from uuid import UUID

import pytest

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSAAAARecord, DNSNSRecord
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.findings import Finding, FindingType
from octopoes.models.ooi.network import IPAddress, IPPort, Network
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import URL, Website, WebURL
from octopoes.models.path import Path
from octopoes.xtdb.query import Aliased, InvalidField, Query


def test_basic_field_where_clause():
    query = Query(Network).where(Network, name="test")
    assert (
        query.format()
        == """{:query {:find [(pull Network [*])] :where [
    [ Network :Network/name "test" ]
    [ Network :object_type "Network" ]]}}"""
    )

    query = query.limit(4)
    assert (
        query.format()
        == """{:query {:find [(pull Network [*])] :where [
    [ Network :Network/name "test" ]
    [ Network :object_type "Network" ]] :limit 4}}"""
    )
    query = query.offset(0)
    assert (
        query.format()
        == """{:query {:find [(pull Network [*])] :where [
    [ Network :Network/name "test" ]
    [ Network :object_type "Network" ]] :limit 4 :offset 0}}"""
    )


def test_reference_field_where_clause():
    query = Query(Network).where(Finding, ooi=Network)
    assert (
        query.format()
        == """{:query {:find [(pull Network [*])] :where [
    [ Finding :Finding/ooi Network ]
    [ Finding :object_type "Finding" ]
    [ Network :object_type "Network" ]]}}"""
    )


def test_remove_duplicates():
    query = Query(Network).where(Finding, ooi=Network)
    assert query == query.where(Finding, ooi=Network)


def test_invalid_fields_name():
    with pytest.raises(InvalidField) as ctx:
        Query(Network).where(Network, ooi=Finding)

    assert ctx.exconly() == 'octopoes.xtdb.query.InvalidField: "ooi" is not a field of Network'

    with pytest.raises(InvalidField) as ctx:
        Query(Network).where(Network, abc="def")

    assert ctx.exconly() == 'octopoes.xtdb.query.InvalidField: "abc" is not a field of Network'


def test_escaping_quotes():
    query = Query(Network).where(Finding, ooi=Network).where(Network, name='test " name')
    assert (
        query.format()
        == """{:query {:find [(pull Network [*])] :where [
    [ Finding :Finding/ooi Network ]
    [ Finding :object_type "Finding" ]
    [ Network :Network/name "test \\" name" ]
    [ Network :object_type "Network" ]]}}"""
    )


def test_invalid_field_types():
    with pytest.raises(InvalidField) as ctx:
        Query(Network).where(Finding, ooi=3)

    assert ctx.exconly() == "octopoes.xtdb.query.InvalidField: value '3' should be a string or an OOI Type"

    with pytest.raises(InvalidField) as ctx:
        Query(Network).where(Finding, ooi=InvalidField)

    assert ctx.exconly() == "octopoes.xtdb.query.InvalidField: <class 'octopoes.xtdb.query.InvalidField'> is not an OOI"


def test_allow_string_for_foreign_keys():
    query = Query(Network).where(Finding, ooi="Network|internet")

    assert (
        query.format()
        == """{:query {:find [(pull Network [*])] :where [
    [ Finding :Finding/ooi "Network|internet" ]
    [ Finding :object_type "Finding" ]
    [ Network :object_type "Network" ]]}}"""
    )


def test_big_multiple_direction_query():
    query = (
        Query(Finding)
        .where(Finding, ooi=Network, finding_type="KATFindingType|KAT-500")
        .where(IPAddress, network=Network)
        .where(IPPort, address=IPAddress)
        .where(IPPort, primary_key="IPPort|internet|xxx:xxx:x|tcp|23")
    )

    assert (
        query.format()
        == """{:query {:find [(pull Finding [*])] :where [
    (or [ IPAddress :IPAddressV4/network Network ] [ IPAddress :IPAddressV6/network Network ] )
    (or [ IPAddress :object_type "IPAddressV4" ] [ IPAddress :object_type "IPAddressV6" ] )
    [ Finding :Finding/finding_type "KATFindingType|KAT-500" ]
    [ Finding :Finding/ooi Network ]
    [ Finding :object_type "Finding" ]
    [ IPPort :IPPort/address IPAddress ]
    [ IPPort :IPPort/primary_key "IPPort|internet|xxx:xxx:x|tcp|23" ]
    [ IPPort :object_type "IPPort" ]]}}"""
    )


def test_create_query_from_path():
    query = Query.from_path(Path.parse("HTTPHeader.resource.website.hostname.network.<ooi [is Finding]"))

    assert (
        query.format()
        == """{:query {:find [(pull Finding [*])] :where [
    [ Finding :Finding/ooi Network ]
    [ Finding :object_type "Finding" ]
    [ HTTPHeader :HTTPHeader/resource HTTPResource ]
    [ HTTPHeader :object_type "HTTPHeader" ]
    [ HTTPResource :HTTPResource/website Website ]
    [ HTTPResource :object_type "HTTPResource" ]
    [ Hostname :Hostname/network Network ]
    [ Hostname :object_type "Hostname" ]
    [ Website :Website/hostname Hostname ]
    [ Website :object_type "Website" ]]}}"""
    )

    query = Query.from_path(Path.parse("IPPort.address.network.<ooi [is Finding]")).where(
        IPPort, primary_key="IPPort|internet|xxx:xxx:x|tcp|23"
    )
    assert (
        query.format()
        == """{:query {:find [(pull Finding [*])] :where [
    (or [ IPAddress :IPAddressV4/network Network ] [ IPAddress :IPAddressV6/network Network ] )
    (or [ IPAddress :object_type "IPAddressV4" ] [ IPAddress :object_type "IPAddressV6" ] )
    [ Finding :Finding/ooi Network ]
    [ Finding :object_type "Finding" ]
    [ IPPort :IPPort/address IPAddress ]
    [ IPPort :IPPort/primary_key "IPPort|internet|xxx:xxx:x|tcp|23" ]
    [ IPPort :object_type "IPPort" ]]}}"""
    )


def test_finding_type_count_query():
    query = Query(FindingType).where(Finding, finding_type=FindingType).pull(FindingType).count(Finding)
    object_type_options = [
        '[ FindingType :object_type "ADRFindingType" ]',
        '[ FindingType :object_type "CAPECFindingType" ]',
        '[ FindingType :object_type "CVEFindingType" ]',
        '[ FindingType :object_type "CWEFindingType" ]',
        '[ FindingType :object_type "KATFindingType" ]',
        '[ FindingType :object_type "RetireJSFindingType" ]',
        '[ FindingType :object_type "SnykFindingType" ]',
    ]
    or_statement_list = " ".join(object_type_options)

    assert (
        query.format()
        == f"""{{:query {{:find [(pull FindingType [*]) (count Finding)] :where [
    (or {or_statement_list} )
    [ Finding :Finding/finding_type FindingType ]
    [ Finding :object_type "Finding" ]]}}}}"""
    )


def test_create_query_from_path_abstract():
    path = Path.parse("IPAddress.<address[is IPPort]")

    query = Query.from_path(path).where(IPAddress, primary_key="test_pk")

    expected_query = """{:query {:find [(pull IPPort [*])] :where [
    (or [ IPAddress :IPAddressV4/primary_key "test_pk" ] [ IPAddress :IPAddressV6/primary_key "test_pk" ] )
    (or [ IPAddress :object_type "IPAddressV4" ] [ IPAddress :object_type "IPAddressV6" ] )
    [ IPPort :IPPort/address IPAddress ]
    [ IPPort :object_type "IPPort" ]]}}"""

    assert query.format() == expected_query


def test_value_for_abstract_class_check():
    Query(IPAddress).where(IPAddress, network=Network).where(Network, name="test")
    Query(IPAddress).where(IPAddress, network=Aliased(Network)).where(Network, name="test")

    with pytest.raises(InvalidField) as ctx:
        Query(IPAddress).where(IPAddress, network=3).where(Network, name="test")

    assert "value '3' for abstract class fields should be a string or an OOI Type" in ctx.exconly()


def test_aliased_query():
    h1 = Aliased(Hostname, UUID("4b4afa7e-5b76-4506-a373-069216b051c2"))
    h2 = Aliased(Hostname, UUID("98076f7a-7606-47ac-85b7-b511ee21ae42"))
    query = (
        Query(DNSAAAARecord)
        .where(DNSAAAARecord, hostname=h1)
        .where(DNSNSRecord, hostname=h1)
        .where(DNSNSRecord, name_server_hostname=h2)
        .where(Website, hostname=h2)
        .where(Website, primary_key="test_pk")
    )

    expected_query = """{:query {:find [(pull DNSAAAARecord [*])] :where [
    [ DNSAAAARecord :DNSAAAARecord/hostname ?4b4afa7e-5b76-4506-a373-069216b051c2 ]
    [ DNSAAAARecord :object_type "DNSAAAARecord" ]
    [ DNSNSRecord :DNSNSRecord/hostname ?4b4afa7e-5b76-4506-a373-069216b051c2 ]
    [ DNSNSRecord :DNSNSRecord/name_server_hostname ?98076f7a-7606-47ac-85b7-b511ee21ae42 ]
    [ DNSNSRecord :object_type "DNSNSRecord" ]
    [ Website :Website/hostname ?98076f7a-7606-47ac-85b7-b511ee21ae42 ]
    [ Website :Website/primary_key "test_pk" ]
    [ Website :object_type "Website" ]]}}"""

    assert query.format() == expected_query


def test_aliased_path_query(mocker):
    """Traverse the Hostname object twice"""

    mocker.patch("octopoes.xtdb.query.uuid4", return_value=UUID("311d6399-4bb4-4830-b077-661cc3f4f2c1"))
    path = Path.parse("Website.hostname.<hostname[is DNSNSRecord].name_server_hostname.<hostname[is DNSAAAARecord]")
    query = Query.from_path(path).where(Website, primary_key="test_pk")

    expected_query = """{:query {:find [(pull DNSAAAARecord [*])] :where [
    [ DNSAAAARecord :DNSAAAARecord/hostname ?311d6399-4bb4-4830-b077-661cc3f4f2c1 ]
    [ DNSAAAARecord :object_type "DNSAAAARecord" ]
    [ DNSNSRecord :DNSNSRecord/hostname Hostname ]
    [ DNSNSRecord :DNSNSRecord/name_server_hostname ?311d6399-4bb4-4830-b077-661cc3f4f2c1 ]
    [ DNSNSRecord :object_type "DNSNSRecord" ]
    [ Website :Website/hostname Hostname ]
    [ Website :Website/primary_key "test_pk" ]
    [ Website :object_type "Website" ]]}}"""

    assert query.format() == expected_query


def test_aliased_query_starting_with_hostname(mocker):
    mocker.patch("octopoes.xtdb.query.uuid4", return_value=UUID("311d6399-4bb4-4830-b077-661cc3f4f2c1"))
    path = Path.parse(
        "Hostname.<hostname[is DNSMXRecord].mail_hostname.<hostname[is DNSARecord].address.<address[is IPPort]"
    )
    query = Query.from_path(path)

    expected_query = """{:query {:find [(pull IPPort [*])] :where [
    [ DNSARecord :DNSARecord/address IPAddressV4 ]
    [ DNSARecord :DNSARecord/hostname ?311d6399-4bb4-4830-b077-661cc3f4f2c1 ]
    [ DNSARecord :object_type "DNSARecord" ]
    [ DNSMXRecord :DNSMXRecord/hostname Hostname ]
    [ DNSMXRecord :DNSMXRecord/mail_hostname ?311d6399-4bb4-4830-b077-661cc3f4f2c1 ]
    [ DNSMXRecord :object_type "DNSMXRecord" ]
    [ IPPort :IPPort/address IPAddressV4 ]
    [ IPPort :object_type "IPPort" ]]}}"""
    assert query.format() == expected_query


def test_build_system_query_with_path_segments(mocker):
    uuid_batch = [uuid.uuid4() for _ in range(3)]
    uuid_mock = mocker.patch("octopoes.xtdb.query.uuid4")
    uuid_mock.side_effect = uuid_batch

    resolved_hostname_alias = Aliased(ResolvedHostname)
    hostname_alias = Aliased(Hostname)

    query = (
        Query(hostname_alias)
        .where(Hostname, primary_key="Hostname|test|example.com")
        .where(ResolvedHostname, hostname=Hostname)
        .where(ResolvedHostname, address=IPAddress)
        .where(resolved_hostname_alias, hostname=hostname_alias)
        .where(resolved_hostname_alias, address=IPAddress)
    )

    uuid_mock.side_effect = uuid_batch
    path_query = Query.from_path(
        Path.parse("Hostname.<hostname[is ResolvedHostname].address.<address[is ResolvedHostname].hostname")
    ).where(Hostname, primary_key="Hostname|test|example.com")

    assert str(query) == str(path_query)
    assert query == path_query

    uuid_mock.side_effect = uuid_batch

    query = (
        Query(Service)
        .where(Hostname, primary_key="Hostname|test|example.com")
        .where(ResolvedHostname, hostname=Hostname)
        .where(ResolvedHostname, address=IPAddress)
        .where(IPPort, address=IPAddress)
        .where(IPService, ip_port=IPPort)
        .where(IPService, service=Service)
    )

    uuid_mock.side_effect = uuid_batch
    path_query = Query.from_path(
        Path.parse(
            "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort].<ip_port [is IPService].service"
        )
    ).where(Hostname, primary_key="Hostname|test|example.com")

    assert str(query) == str(path_query)
    assert query == path_query


def test_build_parth_query_with_multiple_sources(mocker):
    mocker.patch("octopoes.xtdb.query.uuid4", return_value=UUID("311d6399-4bb4-4830-b077-661cc3f4f2c1"))

    query = Query(Website).where_in(Website, primary_key=["test_pk", "second_test_pk"])
    assert (
        query.format()
        == """{:query {:find [(pull Website [*])] :where [
    (or [ Website :Website/primary_key "test_pk" ] [ Website :Website/primary_key "second_test_pk" ] )
    [ Website :object_type "Website" ]]}}"""
    )

    pk = Aliased(Website, field="primary_key")
    query = (
        Query(Website)
        .find(pk)
        .pull(Website)
        .where(Website, primary_key=pk)
        .where_in(Website, primary_key=["test_pk", "second_test_pk"])
    )

    assert (
        query.format()
        == """{:query {:find [?311d6399-4bb4-4830-b077-661cc3f4f2c1?primary_key (pull Website [*])] :where [
    (or [ Website :Website/primary_key "test_pk" ] [ Website :Website/primary_key "second_test_pk" ] )
    [ Website :Website/primary_key ?311d6399-4bb4-4830-b077-661cc3f4f2c1?primary_key ]
    [ Website :object_type "Website" ]]}}"""
    )


def test_build_parth_query_with_multiple_sources_for_abstract_type(mocker):
    mocker.patch("octopoes.xtdb.query.uuid4", return_value=UUID("311d6399-4bb4-4830-b077-661cc3f4f2c1"))

    object_path = Path.parse("IPAddress.network")
    pk = Aliased(IPAddress, field="primary_key")
    query = (
        Query.from_path(object_path)
        .find(pk)
        .pull(IPAddress)
        .where(IPAddress, network=Network)
        .where(IPAddress, primary_key=pk)
        .where_in(IPAddress, primary_key=["1", "2"])
    )
    assert (
        str(query) == "{:query {:find [?311d6399-4bb4-4830-b077-661cc3f4f2c1?primary_key (pull IPAddress [*])] :where ["
        " (or [ IPAddress :IPAddressV4/network Network ] [ IPAddress :IPAddressV6/network Network ] )"
        " (or "
        '[ IPAddress :IPAddressV4/primary_key "1" ] '
        '[ IPAddress :IPAddressV6/primary_key "1" ] '
        '[ IPAddress :IPAddressV4/primary_key "2" ] '
        '[ IPAddress :IPAddressV6/primary_key "2" ] )'
        " (or [ IPAddress :IPAddressV4/primary_key ?311d6399-4bb4-4830-b077-661cc3f4f2c1?primary_key ] "
        "[ IPAddress :IPAddressV6/primary_key ?311d6399-4bb4-4830-b077-661cc3f4f2c1?primary_key ] )"
        ' (or [ IPAddress :object_type "IPAddressV4" ] [ IPAddress :object_type "IPAddressV6" ] )'
        ' [ Network :object_type "Network" ]]}}'
    )


def test_parse_path_concrete_fields_or_abstract_types():
    segments = Path.parse("URL.web_url.netloc.name").segments
    assert len(segments) == 3
    assert segments[0].source_type == URL
    assert segments[0].target_type == WebURL

    assert segments[1].source_type == WebURL
    assert segments[1].target_type == Hostname

    assert segments[2].source_type == Hostname
    assert segments[2].target_type is None
    assert segments[2].property_name == "name"


def test_generic_OOI_query(mocker):
    mocker.patch("uuid.uuid4", return_value=UUID("311d6399-4bb4-4830-b077-661cc3f4f2c1"))

    query = Query().where(OOI, id="test")
    assert str(query) == '{:query {:find [(pull OOI [*])] :where [ [ OOI :xt/id "test" ]]}}'

    query = Query().where_in(OOI, id=["test", "test2"])
    assert (
        str(query) == '{:query {:find [(pull OOI [*])] :where [ (or [ OOI :xt/id "test" ] [ OOI :xt/id "test2" ] )]}}'
    )

    query.pull(OOI, fields="[* {:_reference [*]}]")
    assert (
        str(query) == "{:query {:find [(pull OOI [* {:_reference [*]}])] "
        ':where [ (or [ OOI :xt/id "test" ] [ OOI :xt/id "test2" ] )]}}'
    )
