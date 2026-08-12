import logging
import os
from datetime import datetime, timezone

import pytest

from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddress, IPAddressV4, Network
from octopoes.models.ooi.reports import AssetReport, Report
from octopoes.models.ooi.web import URL
from octopoes.models.path import Path
from octopoes.repositories.ooi_repository import XTDBOOIRepository
from octopoes.repositories.origin_repository import XTDBOriginRepository
from octopoes.xtdb.client import OperationType, XTDBHTTPClient, XTDBSession
from octopoes.xtdb.exceptions import NodeNotFound
from octopoes.xtdb.query import Aliased, Query
from tests.conftest import seed_asset_report, seed_report, seed_system

logger = logging.getLogger(__name__)

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)


def test_node_creation_and_deletion(xtdb_http_client: XTDBHTTPClient):
    xtdb_http_client.create_node()
    status = xtdb_http_client.status()

    assert status.indexVersion == 22
    assert status.consumerState is None
    assert status.kvStore == "xtdb.rocksdb.RocksKv"
    assert status.estimateNumKeys >= 1

    xtdb_http_client.delete_node()

    with pytest.raises(NodeNotFound):
        assert xtdb_http_client.status()


def test_delete_non_existing_node(xtdb_http_client: XTDBHTTPClient):
    with pytest.raises(NodeNotFound):
        xtdb_http_client.delete_node()


def test_query_no_results(xtdb_session: XTDBSession):
    query = Query(Network).where(Network, name="test")

    result = xtdb_session.client.query(query)
    assert result == []


def test_query_simple_filter(xtdb_session: XTDBSession, valid_time: datetime):
    xtdb_session.put(XTDBOOIRepository.serialize(Network(name="testnetwork")), valid_time)

    query = Query(Network).where(Network, name="test")
    result = xtdb_session.client.query(query)
    assert result == []

    xtdb_session.commit()

    query = Query(Network).where(Network, name="test")
    result = xtdb_session.client.query(query)
    assert result == []

    query = Query(Network).where(Network, name="testnetwork")
    result = xtdb_session.client.query(query)
    assert result == [
        [
            {
                "Network/primary_key": "Network|testnetwork",
                "Network/name": "testnetwork",
                "object_type": "Network",
                "user_id": None,
                "xt/id": "Network|testnetwork",
            }
        ]
    ]

    query = """{:query {:find [(pull ?3b1ebf3a-3cc1-4e35-8c5f-e8173e55b623 [*])] :where [
    [ ?3b1ebf3a-3cc1-4e35-8c5f-e8173e55b623 :Network/name "testnetwork" ]
    [ ?3b1ebf3a-3cc1-4e35-8c5f-e8173e55b623 :object_type "Network" ]] limit 50 offset 0}}"""

    assert len(xtdb_session.client.query(query)) == 1


def test_query_not_empty_on_reference_filter_for_hostname(xtdb_session: XTDBSession, valid_time: datetime):
    network = Network(name="testnetwork")
    xtdb_session.put(XTDBOOIRepository.serialize(network), valid_time)
    xtdb_session.put(XTDBOOIRepository.serialize(Hostname(network=network.reference, name="testhostname")), valid_time)
    xtdb_session.put(
        XTDBOOIRepository.serialize(Hostname(network=network.reference, name="secondhostname")), valid_time
    )
    xtdb_session.commit()

    query = Query(Network).where(Hostname, name="testhostname").where(Hostname, network=Network)
    result = xtdb_session.client.query(query)
    assert result == [
        [
            {
                "Network/primary_key": "Network|testnetwork",
                "Network/name": "testnetwork",
                "object_type": "Network",
                "user_id": None,
                "xt/id": "Network|testnetwork",
            }
        ]
    ]

    query = query.where(Network, name="testnetwork")
    result = xtdb_session.client.query(query)
    assert result == [
        [
            {
                "Network/primary_key": "Network|testnetwork",
                "Network/name": "testnetwork",
                "object_type": "Network",
                "user_id": None,
                "xt/id": "Network|testnetwork",
            }
        ]
    ]


def test_query_empty_on_reference_filter_for_wrong_hostname(xtdb_session: XTDBSession, valid_time: datetime):
    network = Network(name="testnetwork")
    network2 = Network(name="testnetwork2")
    xtdb_session.put(XTDBOOIRepository.serialize(network), valid_time)
    xtdb_session.put(XTDBOOIRepository.serialize(network2), valid_time)
    xtdb_session.put(
        XTDBOOIRepository.serialize(Hostname(network=network2.reference, name="secondhostname")), valid_time
    )
    xtdb_session.commit()

    query = Query(Network).where(Network, name="testnetwork").where(Hostname, name="secondhostname")  # No foreign key
    result = xtdb_session.client.query(query)
    assert result == [
        [
            {
                "Network/primary_key": "Network|testnetwork",
                "Network/name": "testnetwork",
                "object_type": "Network",
                "user_id": None,
                "xt/id": "Network|testnetwork",
            }
        ]
    ]

    query = query.where(Hostname, network=Network)  # Add foreign key constraint
    assert xtdb_session.client.query(query) == []

    assert len(xtdb_session.client.query(str(Query(Network)))) == 2


def test_query_where_in(xtdb_session: XTDBSession, valid_time: datetime):
    network = XTDBOOIRepository.serialize(Network(name="testnetwork"))
    network2 = XTDBOOIRepository.serialize(Network(name="testnetwork2"))
    ipv4 = XTDBOOIRepository.serialize(IPAddressV4(network="Network|testnetwork2", address="127.0.0.1"))
    xtdb_session.put(network, valid_time)
    xtdb_session.put(network2, valid_time)
    xtdb_session.put(
        XTDBOOIRepository.serialize(Hostname(network="Network|testnetwork2", name="secondhostname")), valid_time
    )
    xtdb_session.put(ipv4, valid_time)
    xtdb_session.commit()

    query = Query.from_path(Path.parse("Hostname.network")).where_in(Network, name=["testnetwork1"])
    result = xtdb_session.client.query(query)
    assert len(result) == 0

    query = Query.from_path(Path.parse("Hostname.network")).where_in(Network, name=["testnetwork2"])
    result = xtdb_session.client.query(query)
    assert result == [[network2]]

    query = Query.from_path(Path.parse("Hostname.network")).where_in(Network, name=["testnetwork", "testnetwork2"])
    result = xtdb_session.client.query(query)
    assert result == [[network2]]

    query = Query(Network).where_in(Network, primary_key=["Network|testnetwork", "Network|testnetwork2"])
    result = xtdb_session.client.query(query)
    assert result == [[network], [network2]]

    pk = Aliased(Network, field="primary_key")
    query = (
        Query(Network)
        .find(pk)
        .pull(Network)
        .where(Network, primary_key=pk)
        .where_in(Network, primary_key=["Network|testnetwork", "Network|testnetwork2"])
    )
    result = xtdb_session.client.query(query, valid_time)
    assert result == [["Network|testnetwork", network], ["Network|testnetwork2", network2]]

    # router logic
    object_path = Path.parse("Hostname.<hostname[is DNSNSRecord]")
    sources = ["Network|testnetwork", "Network|testnetwork2"]
    source_pk_alias = Aliased(object_path.segments[0].source_type, field="primary_key")
    query = (
        Query.from_path(object_path)
        .find(source_pk_alias)
        .pull(object_path.segments[0].source_type)
        .where(object_path.segments[0].source_type, primary_key=source_pk_alias)
        .where_in(object_path.segments[0].source_type, primary_key=sources)
    )
    assert len(xtdb_session.client.query(query, valid_time)) == 0

    object_path = Path.parse("IPAddress.network")
    pk = Aliased(IPAddress, field="primary_key")
    query = (
        Query.from_path(object_path)
        .find(pk)
        .pull(IPAddress)
        .where(IPAddress, network=Network)
        .where(IPAddress, primary_key=pk)
        .where_in(IPAddress, primary_key=["IPAddressV4|testnetwork2|127.0.0.1", "IPAddressV4|testnetwork|0.0.0.0"])
    )
    assert xtdb_session.client.query(query, valid_time) == [["IPAddressV4|testnetwork2|127.0.0.1", ipv4]]


def test_entity_history(xtdb_session: XTDBSession, valid_time: datetime):
    network = Network(name="testnetwork")
    xtdb_session.put(XTDBOOIRepository.serialize(network), datetime.now(timezone.utc))
    xtdb_session.commit()

    xtdb_session.add((OperationType.DELETE, str(network.reference), datetime.now(timezone.utc)))
    xtdb_session.commit()

    xtdb_session.put(XTDBOOIRepository.serialize(network), datetime.now(timezone.utc))
    xtdb_session.commit()

    history = xtdb_session.client.get_entity_history(str(network.reference), with_docs=True)
    assert len(history) == 3

    assert history[0].document is not None
    assert history[1].document is None
    assert history[2].document is not None


def test_query_for_system_report(
    octopoes_api_connector: OctopoesAPIConnector,
    xtdb_ooi_repository: XTDBOOIRepository,
    xtdb_origin_repository: XTDBOriginRepository,
    xtdb_session: XTDBSession,
    valid_time,
):
    seed_system(xtdb_ooi_repository, xtdb_origin_repository, valid_time)

    # Find all hostnames with the same ip address
    query = Query.from_path(
        Path.parse("Hostname.<hostname[is ResolvedHostname].address.<address[is ResolvedHostname].hostname")
    ).where(Hostname, primary_key="Hostname|test|example.com")
    result = xtdb_session.client.query(query)

    assert len(result) == 10
    pks = [x[0]["Hostname/primary_key"] for x in result]

    assert pks.count("Hostname|test|a.example.com") == 1
    assert pks.count("Hostname|test|b.example.com") == 1
    assert pks.count("Hostname|test|c.example.com") == 2  # Duplicated through ipv6
    assert pks.count("Hostname|test|d.example.com") == 2  # Duplicated through ipv6
    assert pks.count("Hostname|test|e.example.com") == 1
    assert pks.count("Hostname|test|f.example.com") == 1
    assert pks.count("Hostname|test|example.com") == 2  # Duplicated through ipv6

    # Find all services attached to the hostnames ip address
    query = Query.from_path(
        Path.parse(
            "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort].<ip_port [is IPService].service"
        )
    ).where(Hostname, primary_key="Hostname|test|example.com")
    result = xtdb_session.client.query(query)
    assert len(result) == 4

    pks = {x[0]["Service/primary_key"] for x in result}
    assert pks == {"Service|ssh", "Service|smtp", "Service|https", "Service|http"}

    # Queries performed in Rocky's system report
    ips = octopoes_api_connector.query(
        "Hostname.<hostname[is ResolvedHostname].address", valid_time, "Hostname|test|c.example.com"
    )

    ip_services = {}

    for ip in ips:
        ip_services[str(ip.address)] = {
            "hostnames": [
                str(x.name)
                for x in octopoes_api_connector.query(
                    "IPAddress.<address[is ResolvedHostname].hostname", valid_time, ip.reference
                )
            ],
            "services": list(
                {
                    str(x.name)
                    for x in octopoes_api_connector.query(
                        "IPAddress.<address[is IPPort].<ip_port [is IPService].service", valid_time, ip.reference
                    )
                }.union(
                    {
                        str(x.name)
                        for x in octopoes_api_connector.query(
                            "IPAddress.<address[is IPPort].<ooi [is SoftwareInstance].software",
                            valid_time,
                            ip.reference,
                        )
                    }
                )
            ),
            "websites": [
                str(x.hostname)
                for x in octopoes_api_connector.query(
                    "IPAddress.<address[is IPPort].<ip_port [is IPService].<ip_service [is Website]",
                    valid_time,
                    ip.reference,
                )
                if x.hostname == Reference.from_str("Hostname|test|a.example.com")
            ],
        }

    assert len(ips) == 2
    assert len(ip_services["192.0.2.3"]["hostnames"]) == 6
    assert len(ip_services["192.0.2.3"]["services"]) == 4
    assert len(ip_services["192.0.2.3"]["websites"]) == 1
    assert ip_services["192.0.2.3"]["websites"][0] == "Hostname|test|a.example.com"

    assert len(ip_services["3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230"]["hostnames"]) == 4
    assert len(ip_services["3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230"]["services"]) == 1
    assert len(ip_services["3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230"]["websites"]) == 0


def test_query_for_web_system_report(
    octopoes_api_connector: OctopoesAPIConnector,
    xtdb_ooi_repository: XTDBOOIRepository,
    xtdb_origin_repository: XTDBOriginRepository,
    xtdb_session: XTDBSession,
    valid_time: datetime,
):
    seed_system(xtdb_ooi_repository, xtdb_origin_repository, valid_time)
    web_hostname = Hostname(network=Network(name="test").reference, name="example.com")
    second_web_hostname = Hostname(network=Network(name="test").reference, name="a.example.com")

    query = "Hostname.<ooi[is Finding].finding_type"
    assert (
        len(octopoes_api_connector.query(query, valid_time, web_hostname.reference)) == 0
    )  # We should not consider Internetnl finding types

    query = "Hostname.<hostname[is Website].<website[is HTTPResource].<ooi[is Finding].finding_type"
    resources_finding_types = octopoes_api_connector.query(query, valid_time, web_hostname.reference)

    assert len(resources_finding_types) == 1
    ids = [x.id for x in resources_finding_types]
    assert "KAT-NO-CSP" in ids

    query = "Hostname.<netloc[is HostnameHTTPURL].<ooi[is Finding].finding_type"
    web_url_finding_types = octopoes_api_connector.query(query, valid_time, web_hostname.reference)
    assert len(web_url_finding_types) == 1
    assert web_url_finding_types[0].id == "KAT-NO-HTTPS-REDIRECT"

    query = "Hostname.<hostname[is Website].<ooi[is Finding].finding_type"
    assert len(octopoes_api_connector.query(query, valid_time, web_hostname.reference)) == 0
    assert len(octopoes_api_connector.query(query, valid_time, second_web_hostname.reference)) == 1

    query = "Hostname.<hostname[is Website].<website[is SecurityTXT]"
    assert len(octopoes_api_connector.query(query, valid_time, web_hostname.reference)) == 0

    # a.example.com has a SecurityTXT
    assert len(octopoes_api_connector.query(query, valid_time, second_web_hostname.reference)) == 1

    query = "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort]"
    assert len(octopoes_api_connector.query(query, valid_time, web_hostname.reference)) == 4

    query = "Hostname.<hostname[is Website].certificate.<ooi[is Finding].finding_type"
    assert len(octopoes_api_connector.query(query, valid_time, web_hostname.reference)) == 0


def test_query_subclass_fields_and_returning_only_fields(
    octopoes_api_connector: OctopoesAPIConnector,
    xtdb_ooi_repository: XTDBOOIRepository,
    xtdb_origin_repository: XTDBOriginRepository,
    xtdb_session: XTDBSession,
    valid_time: datetime,
):
    seed_system(xtdb_ooi_repository, xtdb_origin_repository, valid_time)

    query = Query.from_path(Path.parse("URL.web_url.network"))
    result = xtdb_session.client.query(query, valid_time)
    assert result == [
        [
            {
                "object_type": "Network",
                "user_id": None,
                "Network/primary_key": "Network|test",
                "Network/name": "test",
                "xt/id": "Network|test",
            }
        ]
    ]

    query = Query.from_path(Path.parse("URL.web_url.scheme"))
    result = xtdb_session.client.query(query, valid_time)
    assert result == [["https"]]

    query = query.where(URL, primary_key="URL|test|https://test.com/security")
    result = xtdb_session.client.query(query, valid_time)
    assert result == [["https"]]

    query = Query.from_path(Path.parse("URL.web_url.netloc")).where(
        URL, primary_key="URL|test|https://test.com/security"
    )
    result = xtdb_session.client.query(query, valid_time)
    assert result == [
        [
            {
                "Hostname/primary_key": "Hostname|test|example.com",
                "object_type": "Hostname",
                "user_id": None,
                "Hostname/network": "Network|test",
                "Hostname/name": "example.com",
                "xt/id": "Hostname|test|example.com",
            }
        ]
    ]

    query = Query.from_path(Path.parse("URL.web_url.netloc.name")).where(
        URL, primary_key="URL|test|https://test.com/security"
    )
    result = xtdb_session.client.query(query, valid_time)
    assert result == [["example.com"]]

    pk = Aliased(URL, field="primary_key")
    query = (
        Query.from_path(Path.parse("URL.web_url.netloc.name"))
        .find(pk, index=0)
        .where(URL, primary_key=pk)
        .where_in(URL, primary_key=["URL|test|https://test.com/security", "URL|test|https://test.com/test"])
    )
    result = xtdb_session.client.query(query, valid_time)
    assert result == [["URL|test|https://test.com/security", "example.com"]]

    result = octopoes_api_connector.query("Network.name", valid_time, "Network|test")
    assert result == ["test"]

    result = octopoes_api_connector.query_many(
        "URL.web_url.netloc.name", valid_time, ["URL|test|https://test.com/security", "URL|test|https://test.com/test"]
    )
    assert result == [("URL|test|https://test.com/security", "example.com")]


def test_order_reports_and_filter_on_parent(
    octopoes_api_connector: OctopoesAPIConnector,
    xtdb_ooi_repository: XTDBOOIRepository,
    xtdb_origin_repository: XTDBOriginRepository,
    xtdb_session: XTDBSession,
    valid_time: datetime,
):
    seed_system(xtdb_ooi_repository, xtdb_origin_repository, valid_time)
    seed_report("test", valid_time, xtdb_ooi_repository, xtdb_origin_repository)

    assert xtdb_session.client.query(Query(Report).count()) == [[1]]
    assert xtdb_ooi_repository.list_reports(valid_time, 0, 2).count == 1

    date = Aliased(Report, field="date_generated")
    query = Query(Report).pull(Report).find(date).where(Report, date_generated=date).order_by(date)

    assert len(xtdb_session.client.query(query)) == 1
    assert len(xtdb_session.client.query(Query(AssetReport))) == 0


def test_ooi_repository_list_reports_with_children(
    octopoes_api_connector: OctopoesAPIConnector,
    xtdb_ooi_repository: XTDBOOIRepository,
    xtdb_origin_repository: XTDBOriginRepository,
    xtdb_session: XTDBSession,
    valid_time: datetime,
):
    seed_system(xtdb_ooi_repository, xtdb_origin_repository, valid_time)
    child = seed_asset_report("child", valid_time, xtdb_ooi_repository, xtdb_origin_repository, "firstchild")
    child2 = seed_asset_report("test", valid_time, xtdb_ooi_repository, xtdb_origin_repository, "secondchild")
    seed_asset_report("test", valid_time, xtdb_ooi_repository, xtdb_origin_repository, "test")
    report = seed_report("test", valid_time, xtdb_ooi_repository, xtdb_origin_repository, input_reports=[child, child2])
    report2 = seed_report("test2", valid_time, xtdb_ooi_repository, xtdb_origin_repository)

    # We filter on Reports and do not fetch the AssetReports
    assert xtdb_ooi_repository.list_reports(valid_time, 0, 2).count == 2
    assert xtdb_ooi_repository.list_reports(valid_time, 0, 1).count == 2
    assert len(xtdb_ooi_repository.list_reports(valid_time, 0, 1).items) == 1
    assert (
        xtdb_ooi_repository.list_reports(valid_time, 0, 2, recipe_id=report.report_recipe.tokenized.recipe_id).count
        == 1
    )
    assert (
        xtdb_ooi_repository.list_reports(valid_time, 0, 2, recipe_id=report2.report_recipe.tokenized.recipe_id).count
        == 1
    )
    recipe_id = report.report_recipe.tokenized.recipe_id
    (listed_report,) = xtdb_ooi_repository.list_reports(valid_time, 0, 1, recipe_id=recipe_id).items

    assert child in listed_report.input_oois
    assert child2 in listed_report.input_oois


def test_query_children_of_reports(
    octopoes_api_connector: OctopoesAPIConnector,
    xtdb_ooi_repository: XTDBOOIRepository,
    xtdb_origin_repository: XTDBOriginRepository,
    xtdb_session: XTDBSession,
    valid_time: datetime,
):
    seed_system(xtdb_ooi_repository, xtdb_origin_repository, valid_time)
    child = seed_asset_report("child", valid_time, xtdb_ooi_repository, xtdb_origin_repository, "firstchild")
    child2 = seed_asset_report("test", valid_time, xtdb_ooi_repository, xtdb_origin_repository, "secondchild")
    seed_asset_report("test", valid_time, xtdb_ooi_repository, xtdb_origin_repository, "test")
    report = seed_report("test", valid_time, xtdb_ooi_repository, xtdb_origin_repository, input_reports=[child, child2])
    report2 = seed_report("test2", valid_time, xtdb_ooi_repository, xtdb_origin_repository)

    # See https://v1-docs.xtdb.com/language-reference/1.24.3/datalog-queries/#pull for documentation about joins in a
    # pull statement.
    query = Query(Report).pull(Report, fields="[* {:Report/input_oois [*]}]")
    results = xtdb_session.client.query(query)

    # The Report is hydrated with its input OOIs
    assert [xtdb_ooi_repository.serialize(report2)] in results
    assert [
        xtdb_ooi_repository.serialize(report)
        | {"Report/input_oois": [xtdb_ooi_repository.serialize(child), xtdb_ooi_repository.serialize(child2)]}
    ] in results

    hydrated_report = octopoes_api_connector.get_report(report.reference, valid_time)
    assert hydrated_report.to_report() == report
    assert hydrated_report.input_oois == [child, child2]
