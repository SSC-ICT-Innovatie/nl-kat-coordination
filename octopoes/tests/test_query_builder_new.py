from unittest import TestCase

from octopoes.models.origin import Origin
from octopoes.xtdb import Datamodel, FieldSet, ForeignKey
from octopoes.xtdb.query_builder import generate_pull_query
from octopoes.xtdb.related_field_generator import RelatedFieldNode

sample_data_model = {
    "Certificate": {"signed_by": {"Certificate"}, "website": {"Hostname"}},
    "CveFindingType": {},
    "CweFindingType": {},
    "DnsARecord": {"Hostname": {"Hostname"}, "IpAddressV4": {"IpAddressV4"}},
    "DnsAaaaRecord": {"Hostname": {"Hostname"}, "IpAddressV6": {"IpAddressV6"}},
    "DnsMxRecord": {"Hostname": {"Hostname"}, "MailHostname": {"Hostname"}},
    "DnsTxtRecord": {"Hostname": {"Hostname"}},
    "DnsZone": {
        "DnsNameServerHostname": {"Hostname"},
        "DnsSoaHostname": {"Hostname"},
        "Network": {"Network"},
        "ParentDnsZone": {"DnsZone"},
    },
    "Finding": {
        "FindingType": {"KatFindingType", "CveFindingType"},
        "OOI": {
            "Certificate",
            "CveFindingType",
            "CweFindingType",
            "DnsARecord",
            "DnsAaaaRecord",
            "DnsMxRecord",
            "DnsTxtRecord",
            "DnsZone",
            "Hostname",
            "IpAddressV4",
            "IpAddressV6",
            "IpPort",
            "IpService",
            "KatFindingType",
            "Network",
            "Service",
            "Software",
            "Url",
            "Website",
        },
    },
    "Hostname": {"DnsZone": {"DnsZone"}, "Network": {"Network"}},
    "IpAddressV4": {"Network": {"Network"}},
    "IpAddressV6": {"Network": {"Network"}},
    "IpPort": {"IpAddress": {"IpAddressV4", "IpAddressV6"}},
    "IpService": {"IpPort": {"IpPort"}, "Service": {"Service"}},
    "Job": {
        "oois": {
            "Certificate",
            "CveFindingType",
            "CweFindingType",
            "DnsARecord",
            "DnsAaaaRecord",
            "DnsMxRecord",
            "DnsTxtRecord",
            "DnsZone",
            "Hostname",
            "IpAddressV4",
            "IpAddressV6",
            "IpPort",
            "IpService",
            "KatFindingType",
            "Network",
            "Service",
            "Software",
            "Url",
            "Website",
        }
    },
    "KatFindingType": {},
    "Network": {},
    "Service": {},
    "Software": {"IpService": {"IpService"}},
    "Url": {"Website": {"Website"}},
    "Website": {"Hostname": {"Hostname"}, "IpService": {"IpService"}},
}

entities = {}
for entity, relations in sample_data_model.items():
    fks = []
    for field_name, related_entities in relations.items():
        fks.append(
            ForeignKey(
                source_entity=entity,
                attr_name=field_name,
                related_entities=related_entities,
                reverse_name=f"{entity}/_{field_name}",
            )
        )
    entities[entity] = fks

datamodel = Datamodel(entities=entities)


class QueryNodeTest(TestCase):
    def test_QueryNode_1_deep_success(self):
        root = RelatedFieldNode(data_model=datamodel, object_types={"Job"})
        root.build_tree(1)

        self.assertEqual({}, root.relations_in)
        self.assertEqual(
            {
                "Certificate",
                "CveFindingType",
                "CweFindingType",
                "DnsARecord",
                "DnsAaaaRecord",
                "DnsMxRecord",
                "DnsTxtRecord",
                "DnsZone",
                "Hostname",
                "IpAddressV4",
                "IpAddressV6",
                "IpPort",
                "IpService",
                "KatFindingType",
                "Network",
                "Service",
                "Software",
                "Url",
                "Website",
            },
            root.relations_out[("Job", "oois")].object_types,
            "build_tree of 1 level deep should have created a QueryNode with set of related types",
        )

    def test_QueryNode_2_deep_success(self):
        root = RelatedFieldNode(data_model=datamodel, object_types={"IpPort"})
        root.build_tree(2)

        # Check IPV4/IPV6 node
        address_node = root.relations_out[("IpPort", "IpAddress")]
        self.assertEqual({"IpAddressV4", "IpAddressV6"}, address_node.object_types)

        # Check IPV4/IPV6 node (Network)
        network_node_from_ipv4 = address_node.relations_out[("IpAddressV4", "Network")]
        self.assertEqual({"Network"}, network_node_from_ipv4.object_types)
        network_node_from_ipv6 = address_node.relations_out[("IpAddressV6", "Network")]
        self.assertEqual({"Network"}, network_node_from_ipv6.object_types)

        # Check IPV4/IPV6 incoming nodes
        dns_a_record_node = address_node.relations_in[("DnsARecord", "IpAddressV4", "DnsARecord/_IpAddressV4")]
        self.assertEqual({"DnsARecord"}, dns_a_record_node.object_types)

        dns_aaaa_record_node = address_node.relations_in[("DnsAaaaRecord", "IpAddressV6", "DnsAaaaRecord/_IpAddressV6")]
        self.assertEqual({"DnsAaaaRecord"}, dns_aaaa_record_node.object_types)

        finding_node = address_node.relations_in[("Finding", "OOI", "Finding/_OOI")]
        self.assertEqual({"Finding"}, finding_node.object_types)

        job_node = address_node.relations_in[("Job", "oois", "Job/_oois")]
        self.assertEqual({"Job"}, job_node.object_types)

    def test_QueryNode_3_deep_dont_return_previous_relation_success(self):
        root = RelatedFieldNode(data_model=datamodel, object_types={"IpPort"})
        root.build_tree(3)

        # Check IPV4/IPV6 node
        address_node = root.relations_out[("IpPort", "IpAddress")]

        self.assertNotIn(("IpPort", "IpAddress"), address_node.relations_in)

    def test_QueryNode_multiple_root_types_success(self):
        root = RelatedFieldNode(data_model=datamodel, object_types={"IpAddressV4", "IpAddressV6"})
        root.build_tree(1)

        expected = {
            ("IpPort", "IpAddress", "IpPort/_IpAddress"): RelatedFieldNode(
                data_model=datamodel, object_types={"IpPort"}
            ),
            ("DnsARecord", "IpAddressV4", "DnsARecord/_IpAddressV4"): RelatedFieldNode(
                data_model=datamodel, object_types={"DnsARecord"}
            ),
            ("DnsAaaaRecord", "IpAddressV6", "DnsAaaaRecord/_IpAddressV6"): RelatedFieldNode(
                data_model=datamodel, object_types={"DnsAaaaRecord"}
            ),
            ("Finding", "OOI", "Finding/_OOI"): RelatedFieldNode(data_model=datamodel, object_types={"Finding"}),
            ("Job", "oois", "Job/_oois"): RelatedFieldNode(data_model=datamodel, object_types={"Job"}),
        }

        self.assertEqual(expected, root.relations_in)

    def test_generate_query_sucess(self):
        # Query related objects
        field_node = RelatedFieldNode(data_model=datamodel, object_types={"IpAddressV4"})
        field_node.build_tree(1)

        query = generate_pull_query(
            FieldSet.ALL_FIELDS, {"xt/id": "IpAddressV4|internet|1.1.1.1"}, field_node=field_node
        )

        expected_query = (
            "{:query {:find [(pull ?e [* {(:DnsARecord/_IpAddressV4 {:as DnsARecord/_IpAddressV4}) [*]} "
            "{(:Finding/_OOI {:as Finding/_OOI}) [*]} {(:IpAddressV4/Network {:as Network}) [*]} "
            "{(:IpPort/_IpAddress {:as IpPort/_IpAddress}) [*]} {(:Job/_oois {:as Job/_oois}) [*]}])] "
            ':in [_xt_id] :where [[?e :xt/id _xt_id]]   } :in-args [ "IpAddressV4|internet|1.1.1.1" ]}'
        )
        self.assertEqual(expected_query, query)

    def test_escape_injection_success(self):
        query = generate_pull_query(FieldSet.ALL_FIELDS, where={"attr_1": 'test_value_with_quotes" and injection'})

        expected_query = (
            "{:query {:find [(pull ?e [*])] :in [_attr_1] :where [[?e :attr_1 _attr_1]]   } "
            ':in-args [ "test_value_with_quotes\\" and injection" ]}'
        )
        self.assertEqual(expected_query, query)

    def test_get_origin_by_task_id(self):
        query = generate_pull_query(
            FieldSet.ALL_FIELDS, {"task_id": "5c864d45a4364a81a5fecfd8b359cf9d", "type": Origin.__name__}
        )

        expected_query = (
            "{:query {:find [(pull ?e [*])] :in [_task_id _type] :where [[?e :task_id _task_id] "
            '[?e :type _type]]   } :in-args [ "5c864d45a4364a81a5fecfd8b359cf9d" "Origin" ]}'
        )
        self.assertEqual(expected_query, query)
