from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

import structlog
from bits.definitions import BitDefinition
from httpx import HTTPStatusError, codes
from pydantic import RootModel, TypeAdapter

from octopoes.config.settings import (
    DEFAULT_LIMIT,
    DEFAULT_OFFSET,
    DEFAULT_SCAN_LEVEL_FILTER,
    DEFAULT_SCAN_PROFILE_TYPE_FILTER,
    Settings,
)
from octopoes.events.events import OOIDBEvent, OperationType
from octopoes.events.manager import EventManager
from octopoes.models import OOI, Reference, ScanLevel, ScanProfileType
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.findings import Finding, FindingType, RiskLevelSeverity
from octopoes.models.ooi.reports import HydratedReport, Report, ReportRecipe
from octopoes.models.pagination import Paginated
from octopoes.models.path import Direction, Path, Segment, get_paths_to_neighours
from octopoes.models.transaction import TransactionRecord
from octopoes.models.tree import ReferenceNode, ReferenceTree
from octopoes.models.types import get_concrete_types, get_relation, get_relations, to_concrete, type_by_name
from octopoes.repositories.repository import Repository
from octopoes.xtdb import Datamodel, FieldSet, ForeignKey
from octopoes.xtdb.client import OperationType as XTDBOperationType
from octopoes.xtdb.client import XTDBSession
from octopoes.xtdb.query import Aliased, Query
from octopoes.xtdb.query_builder import generate_pull_query, str_val
from octopoes.xtdb.related_field_generator import RelatedFieldNode

logger = structlog.get_logger(__name__)
settings = Settings()


def merge_ooi(ooi_new: OOI, ooi_old: OOI) -> tuple[OOI, bool]:
    data_old = ooi_old.model_dump()
    data_new = ooi_new.model_dump()

    # Trim new None values
    clean_new = {key: val for key, val in data_new.items() if val is not None}

    changed = False
    for key, value in clean_new.items():
        if key in data_old and data_old[key] != value:
            changed = True
            break

    data_old.update(clean_new)
    return ooi_new.__class__.model_validate(data_old), changed


class OOIRepository(Repository):
    def __init__(self, event_manager: EventManager):
        self.event_manager = event_manager

    def get(self, reference: Reference, valid_time: datetime) -> OOI:
        raise NotImplementedError

    def get_history(
        self,
        reference: Reference,
        *,
        sort_order: str = "asc",  # Or: "desc"
        with_docs: bool = False,
        has_doc: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
        indices: list[int] | None = None,
    ) -> list[TransactionRecord]:
        raise NotImplementedError

    def load_bulk(self, references: set[Reference], valid_time: datetime) -> dict[str, OOI]:
        raise NotImplementedError

    def load_bulk_as_list(self, references: set[Reference], valid_time: datetime) -> list[OOI]:
        raise NotImplementedError

    def get_neighbours(
        self, reference: Reference, valid_time: datetime, paths: set[Path] | None = None
    ) -> dict[Path, list[OOI]]:
        raise NotImplementedError

    def list_oois(
        self,
        types: set[type[OOI]],
        valid_time: datetime,
        offset: int = 0,
        limit: int = 20,
        scan_levels: set[ScanLevel] = DEFAULT_SCAN_LEVEL_FILTER,
        scan_profile_types: set[ScanProfileType] = DEFAULT_SCAN_PROFILE_TYPE_FILTER,
        search_string: str | None = None,
        order_by: Literal["scan_level", "object_type"] = "object_type",
        asc_desc: Literal["asc", "desc"] = "asc",
    ) -> Paginated[OOI]:
        raise NotImplementedError

    def list_oois_by_object_types(self, types: set[type[OOI]], valid_time: datetime) -> list[OOI]:
        raise NotImplementedError

    def list_random(
        self, valid_time: datetime, amount: int = 1, scan_levels: set[ScanLevel] = DEFAULT_SCAN_LEVEL_FILTER
    ) -> list[OOI]:
        raise NotImplementedError

    def list_neighbours(self, references: set[Reference], paths: set[Path], valid_time: datetime) -> set[OOI]:
        raise NotImplementedError

    def save(self, ooi: OOI, valid_time: datetime, end_valid_time: datetime | None = None) -> None:
        raise NotImplementedError

    def delete_if_exists(self, reference: Reference, valid_time: datetime) -> None:
        raise NotImplementedError

    def delete(self, reference: Reference, valid_time: datetime) -> None:
        raise NotImplementedError

    def get_tree(
        self, reference: Reference, valid_time: datetime, search_types: set[type[OOI]] | None = None, depth: int = 1
    ) -> ReferenceTree:
        raise NotImplementedError

    def list_oois_without_scan_profile(self, valid_time: datetime) -> set[Reference]:
        raise NotImplementedError

    def count_findings_by_severity(self, valid_time: datetime) -> Counter:
        raise NotImplementedError

    def list_findings(
        self,
        severities: set[RiskLevelSeverity],
        valid_time: datetime,
        exclude_muted: bool = False,
        only_muted: bool = False,
        offset: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        search_string: str | None = None,
        order_by: Literal["score", "finding_type"] = "score",
        asc_desc: Literal["asc", "desc"] = "desc",
    ) -> Paginated[Finding]:
        raise NotImplementedError

    def list_reports(
        self, valid_time: datetime, offset: int, limit: int, recipe_id: UUID | None = None, ignore_count: bool = False
    ) -> Paginated[HydratedReport]:
        raise NotImplementedError

    def get_report(self, valid_time: datetime, report_id: str | Reference) -> HydratedReport:
        raise NotImplementedError

    def get_bit_configs(self, source: OOI, bit_definition: BitDefinition, valid_time: datetime) -> list[Config]:
        raise NotImplementedError

    def list_related(self, ooi: OOI, path: Path, valid_time: datetime) -> list[OOI]:
        raise NotImplementedError

    def query(
        self, query: str | Query, valid_time: datetime, to_type: type[OOI] | None = None
    ) -> list[OOI | tuple | dict[Any, Any]]:
        raise NotImplementedError


class XTDBReferenceNode(RootModel):
    root: dict[str, str | list[XTDBReferenceNode] | XTDBReferenceNode]

    def to_reference_node(self, pk_prefix: str) -> ReferenceNode | None:
        if not self.root:
            return None
        # Apparently relations can be joined to Null values..?!?
        if pk_prefix not in self.root:
            return None
        reference = Reference.from_str(cast(str, self.root.pop(pk_prefix)))
        children = {}
        for name, value in self.root.items():
            if isinstance(value, XTDBReferenceNode):
                sub_nodes = [value.to_reference_node(pk_prefix)]
            elif isinstance(value, list | set):
                sub_nodes = [val_.to_reference_node(pk_prefix) for val_ in value]
            sub_nodes = [node for node in sub_nodes if node is not None]
            if sub_nodes:
                children[name] = sub_nodes
        return ReferenceNode(reference=reference, children=children)


entities = {}
for ooi_type_ in get_concrete_types():
    fks = []
    for field_name, related in get_relations(ooi_type_).items():
        related_entities = {r.__name__ for r in to_concrete({related})}
        fks.append(
            ForeignKey(
                source_entity=ooi_type_.get_object_type(),
                attr_name=field_name,
                related_entities=related_entities,
                reverse_name=ooi_type_.get_reverse_relation_name(field_name),
            )
        )
    entities[ooi_type_.get_object_type()] = fks

datamodel = Datamodel(entities=entities)


def escape_string(string):
    escaped_string = re.sub(r'(["\\])', r"\\\1", string)
    return escaped_string


class XTDBOOIRepository(OOIRepository):
    pk_prefix = "xt/id"

    def __init__(self, event_manager: EventManager, session: XTDBSession):
        super().__init__(event_manager)
        self.session = session

    def commit(self):
        self.session.commit()

    @classmethod
    def serialize(cls, ooi: OOI) -> dict[str, Any]:
        # export model with pydantic serializers
        export = json.loads(ooi.model_dump_json())

        # prefix fields, but not object_type
        export.pop("object_type")
        user_id = export.pop("user_id", None)
        export = {f"{ooi.__class__.__name__}/{key}": value for key, value in export.items() if value is not None}

        export["object_type"] = ooi.__class__.__name__
        export["user_id"] = user_id
        export[cls.pk_prefix] = ooi.primary_key

        return export

    @classmethod
    def deserialize(cls, data: dict[str, Any], to_type: type[OOI] | None = None) -> OOI:
        if "object_type" not in data:
            raise ValueError("Data is missing object_type")

        object_cls = type_by_name(data["object_type"])
        object_cls = to_type or object_cls
        user_id = data.get("user_id")

        # remove type prefixes
        stripped = {
            key.split("/")[1]: value
            for key, value in data.items()
            if key not in [cls.pk_prefix, "user_id", "object_type", "_reference"]
        }
        stripped["user_id"] = user_id

        if scan_profiles := data.get("_reference", []):
            stripped["scan_profile"] = scan_profiles[0]

        return object_cls.model_validate(stripped)

    def get(self, reference: Reference, valid_time: datetime) -> OOI:
        try:
            res = self.session.client.get_entity(str(reference), valid_time)
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise ObjectNotFoundException(str(reference))

            raise

        return self.deserialize(res)

    def get_history(
        self,
        reference: Reference,
        *,
        sort_order: str = "asc",  # Or: "desc"
        with_docs: bool = False,
        has_doc: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
        indices: list[int] | None = None,
    ) -> list[TransactionRecord]:
        try:
            return self.session.client.get_entity_history(
                str(reference),
                sort_order=sort_order,
                with_docs=with_docs,
                has_doc=has_doc,
                offset=offset,
                limit=limit,
                indices=indices,
            )
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise ObjectNotFoundException(str(reference))

            raise

    def load_bulk(self, references: set[Reference], valid_time: datetime) -> dict[str, OOI]:
        oois = self.load_bulk_as_list(references, valid_time)
        return {ooi.primary_key: ooi for ooi in oois}

    def load_bulk_as_list(self, references: set[Reference], valid_time: datetime) -> list[OOI]:
        if not references:
            return []

        query = Query().where_in(OOI, id=references).pull(OOI, fields="[* {:_reference [*]}]")
        return [self.deserialize(x[0]) for x in self.session.client.query(query, valid_time)]

    def list_oois(
        self,
        types: set[type[OOI]],
        valid_time: datetime,
        offset: int = 0,
        limit: int = 20,
        scan_levels: set[ScanLevel] = DEFAULT_SCAN_LEVEL_FILTER,
        scan_profile_types: set[ScanProfileType] = DEFAULT_SCAN_PROFILE_TYPE_FILTER,
        search_string: str | None = None,
        order_by: Literal["scan_level", "object_type"] = "object_type",
        asc_desc: Literal["asc", "desc"] = "asc",
    ) -> Paginated[OOI]:
        types = to_concrete(types)

        search_statement = (
            f"""[?e :xt/id ?id]
                                [(clojure.string/includes? ?id \"{escape_string(search_string)}\")]"""
            if search_string
            else ""
        )

        order_statement = f":order-by [[_{order_by} :{asc_desc}]]"

        count_query = """
                {{
                    :query {{
                        :find [(count ?e)]
                        :in [[_object_type ...] [_scan_level ...] [_scan_profile_type ...]]
                        :where [[?e :object_type _object_type]
                                [?scan_profile :type "ScanProfile"]
                                [?scan_profile :reference ?e]
                                [?scan_profile :level _scan_level]
                                [?scan_profile :scan_profile_type _scan_profile_type]
                                {search_statement}]
                    }}
                    :in-args [[{object_types}], [{scan_levels}], [{scan_profile_types}]]
                }}
                """.format(
            object_types=" ".join(map(lambda t: str_val(t.get_object_type()), types)),
            scan_levels=" ".join([str(scan_level.value) for scan_level in scan_levels]),
            scan_profile_types=" ".join([str_val(scan_profile_type.value) for scan_profile_type in scan_profile_types]),
            search_statement=search_statement,
        )

        res_count = self.session.client.query(count_query, valid_time)
        count = res_count[0][0] if res_count else 0

        data_query = """
                {{
                    :query {{
                        :find [(pull ?e [*]) _object_type _scan_level]
                        :in [[_object_type ...] [_scan_level ...]  [_scan_profile_type ...]]
                        :where [[?e :object_type _object_type]
                                [?scan_profile :type "ScanProfile"]
                                [?scan_profile :reference ?e]
                                [?scan_profile :level _scan_level]
                                [?scan_profile :scan_profile_type _scan_profile_type]
                                {search_statement}]
                        {order_statement}
                        :limit {limit}
                        :offset {offset}
                    }}
                    :in-args [[{object_types}], [{scan_levels}], [{scan_profile_types}]]
                }}
        """.format(
            object_types=" ".join(map(lambda t: str_val(t.get_object_type()), types)),
            scan_levels=" ".join([str(scan_level.value) for scan_level in scan_levels]),
            scan_profile_types=" ".join([str_val(scan_profile_type.value) for scan_profile_type in scan_profile_types]),
            search_statement=search_statement,
            order_statement=order_statement,
            limit=limit,
            offset=offset,
        )

        res = self.session.client.query(data_query, valid_time)
        oois = [self.deserialize(x[0]) for x in res]
        return Paginated(count=count, items=oois)

    def list_oois_by_object_types(self, types: set[type[OOI]], valid_time: datetime) -> list[OOI]:
        types = to_concrete(types)
        data_query = """
                {{
                    :query {{
                        :find [(pull ?e [*])]
                        :in [[_object_type ...]]
                        :where [[?e :object_type _object_type]]
                    }}
                    :in-args [[{object_types}]]
                }}
        """.format(object_types=" ".join(map(lambda t: str_val(t.get_object_type()), types)))
        return [self.deserialize(x[0]) for x in self.session.client.query(data_query, valid_time)]

    def list_random(
        self, valid_time: datetime, amount: int = 1, scan_levels: set[ScanLevel] = DEFAULT_SCAN_LEVEL_FILTER
    ) -> list[OOI]:
        query = """
            {{
                :query {{
                    :find [(rand {amount} ?id)]
                    :in [[_scan_level ...]]
                    :where [
                        [?e :xt/id ?id]
                        [?e :object_type]
                        [?scan_profile :type "ScanProfile"]
                        [?scan_profile :reference ?e]
                        [?scan_profile :level _scan_level]
                    ]
                }}
                :in-args [[{scan_levels}]]
            }}
            """.format(amount=amount, scan_levels=" ".join([str(scan_level.value) for scan_level in scan_levels]))

        res = self.session.client.query(query, valid_time)
        if not res:
            return []
        references = {Reference.from_str(reference) for reference in res[0][0]}
        return list(self.load_bulk(references, valid_time).values())

    def get_tree(
        self, reference: Reference, valid_time: datetime, search_types: set[type[OOI]] | None = None, depth: int = 1
    ) -> ReferenceTree:
        if search_types is None:
            search_types = {OOI}
        concrete_search_types = to_concrete(search_types)

        results = self._get_tree_level({reference}, depth=depth, valid_time=valid_time)

        try:
            reference_node = results[0]
        except IndexError:
            raise ObjectNotFoundException(str(reference))

        reference_node.filter_children(lambda child_node: child_node.reference.class_type in concrete_search_types)

        store = self.load_bulk(reference_node.collect_references(), valid_time)
        return ReferenceTree(root=reference_node, store=store)

    def _get_related_objects(self, references: set[Reference], valid_time: datetime | None) -> list[ReferenceNode]:
        """
        Returns a Reference node for each reference, containing the 1-depth related objects
        """
        ooi_classes = {ooi.class_ for ooi in references}
        ooi_ids = [str(reference) for reference in references]
        field_node = RelatedFieldNode(data_model=datamodel, object_types=ooi_classes)
        field_node.build_tree(1)
        query = generate_pull_query(FieldSet.ONLY_ID, {self.pk_prefix: ooi_ids}, field_node=field_node)
        res = self.session.client.query(query, valid_time=valid_time)
        res = [element[0] for element in res]
        xtdb_reference_root_nodes = TypeAdapter(list[XTDBReferenceNode]).validate_python(res)
        return [x.to_reference_node(self.pk_prefix) for x in xtdb_reference_root_nodes]

    def _get_tree_level(
        self,
        references: set[Reference],
        depth: int = 1,
        exclude: set[Reference] | None = None,
        valid_time: datetime | None = None,
    ) -> list[ReferenceNode]:
        if depth == 0 or not references:
            return []

        if exclude is None:
            exclude = set()

        # Query 1-depth related objects
        reference_nodes = self._get_related_objects(references, valid_time=valid_time)

        # Filter exclusions from results
        for reference_node in reference_nodes:
            reference_node.filter_children(lambda child: child.reference not in exclude)

        if depth == 1:
            return reference_nodes

        # Next depth = children except non-traversable
        deeper_references: set[Reference] = set()
        for reference_node in reference_nodes:
            for child_nodes in reference_node.children.values():
                deeper_references.update([child.reference for child in child_nodes])
        deeper_references = {reference for reference in deeper_references if reference.class_type.traversable()}

        # Query next level
        exclude.update(references)
        deeper_result = self._get_tree_level(deeper_references, depth=depth - 1, exclude=exclude, valid_time=valid_time)

        # Replace flat results with recursed results
        deeper_lookup = {node.reference: node for node in deeper_result}
        for node in reference_nodes:
            node.children = {
                attr_name: [deeper_lookup.get(child.reference, child) for child in children]
                for attr_name, children in node.children.items()
            }

        return reference_nodes

    @classmethod
    def decode_segment(cls, encoded_segment: str) -> Segment:
        source_type_name, property_name = encoded_segment.split("/")
        relation_owner_type = type_by_name(source_type_name)

        if property_name.startswith("_"):
            direction = Direction.INCOMING
            property_name = property_name[1:]
            target_relation = get_relation(relation_owner_type, property_name)
            return Segment(target_relation, direction, property_name, relation_owner_type)
        else:
            direction = Direction.OUTGOING
            target_relation = get_relation(relation_owner_type, property_name)
            return Segment(relation_owner_type, direction, property_name, target_relation)

    @classmethod
    def construct_neighbour_query(cls, reference: Reference, paths: set[Path] | None = None) -> str:
        if paths is None:
            paths = get_paths_to_neighours(reference.class_type)

        encoded_segments = [path.segments[0].encode() for path in sorted(paths)]
        segment_query_sections = [f"{{:{s} [*]}}" for s in encoded_segments]

        query = """{{
                    :query {{
                        :find [
                            (pull ?e [
                                :xt/id
                                {related_fields}
                            ])
                        ]
                        :in [[ _xt_id ... ]]
                        :where [[?e :xt/id _xt_id]]
                    }}
                    :in-args [["{reference}"]]
                }}""".format(reference=reference, related_fields=" ".join(segment_query_sections))

        return query

    @classmethod
    def construct_neighbour_query_multi(cls, references: set[Reference], paths: set[Path]) -> str:
        encoded_segments = [path.segments[0].encode() for path in sorted(paths)]
        segment_query_sections = [f"{{:{s} [*]}}" for s in encoded_segments]

        query = """{{
                        :query {{
                            :find [
                                (pull ?e [
                                    {related_fields}
                                ])
                            ]
                            :in [[ _xt_id ... ]]
                            :where [[?e :xt/id _xt_id] [?e :object_type]]
                        }}
                        :in-args [[{reference}]]
                    }}""".format(
            reference=" ".join(map(str_val, references)), related_fields=" ".join(segment_query_sections)
        )

        return query

    def get_neighbours(
        self, reference: Reference, valid_time: datetime, paths: set[Path] | None = None
    ) -> dict[Path, list[OOI]]:
        query = self.construct_neighbour_query(reference, paths)

        response = self.session.client.query(query, valid_time=valid_time)

        try:
            response_data = response[0][0]
        except IndexError:
            return {}

        ret = {}
        for key, value in response_data.items():
            if key == "xt/id" or value == {}:
                continue
            path = Path([self.decode_segment(key)])
            if isinstance(value, list):
                ret[path] = [self.deserialize(serialized) for serialized in value]
            else:
                ret[path] = [self.deserialize(value)]

        return ret

    def list_neighbours(self, references: set[Reference], paths: set[Path], valid_time: datetime) -> set[OOI]:
        query = self.construct_neighbour_query_multi(references, paths)

        response = self.session.client.query(query, valid_time=valid_time)

        neighbours = set()

        for row in response:
            col = row[0]
            for value in col.values():
                if value:
                    if isinstance(value, list):
                        for serialized in value:
                            neighbours.add(self.deserialize(serialized))
                    else:
                        neighbours.add(self.deserialize(value))

        return neighbours

    def save(self, ooi: OOI, valid_time: datetime, end_valid_time: datetime | None = None) -> None:
        # retrieve old ooi
        try:
            old_ooi = self.get(ooi.reference, valid_time=valid_time)
        except ObjectNotFoundException:
            old_ooi = None

        new_ooi = ooi
        if old_ooi is not None:
            new_ooi, changed = merge_ooi(ooi, old_ooi)
            # Nothing changed, no need to save
            if not changed:
                return

        # save ooi with expiry
        self.session.add((XTDBOperationType.PUT, self.serialize(new_ooi), valid_time))
        if end_valid_time is not None:
            self.session.add((XTDBOperationType.DELETE, str(ooi.reference), end_valid_time))

        # Update event, instead of create
        event = OOIDBEvent(
            operation_type=OperationType.CREATE if old_ooi is None else OperationType.UPDATE,
            valid_time=valid_time,
            old_data=old_ooi,
            new_data=new_ooi,
            client=self.event_manager.client,
        )

        # After transaction, send event
        self.session.listen_post_commit(lambda: self.event_manager.publish(event))

    def delete_if_exists(self, reference: Reference, valid_time: datetime) -> None:
        try:
            self.delete(reference, valid_time)
        except ObjectNotFoundException:
            return

    def delete(self, reference: Reference, valid_time: datetime) -> None:
        ooi = self.get(reference, valid_time=valid_time)

        self.session.add((XTDBOperationType.DELETE, str(reference), valid_time))

        event = OOIDBEvent(
            operation_type=OperationType.DELETE, valid_time=valid_time, old_data=ooi, client=self.event_manager.client
        )
        self.session.listen_post_commit(lambda: self.event_manager.publish(event))

    def list_oois_without_scan_profile(self, valid_time: datetime) -> set[Reference]:
        query = """
            {:query {
             :find [?ooi]
             :where [[?ooi :object_type ?t]
                    (not-join [?ooi] [?scan_profile :reference ?ooi] [?scan_profile :type "ScanProfile"])] }}
        """
        response = self.session.client.query(query, valid_time=valid_time)
        return {Reference.from_str(row[0]) for row in response}

    def count_findings_by_severity(self, valid_time: datetime) -> Counter:
        severity_counts = Counter({severity: 0 for severity in RiskLevelSeverity})

        query = """
            {:query {
                :find [?finding_type (pull ?finding_type [*]) (count ?finding)]
                :where [
                    [?finding :Finding/finding_type ?finding_type]
                    (not-join [?finding] [?muted_finding :MutedFinding/finding ?finding])
                    ]}}
        """

        for finding_type_name, finding_type_object, finding_count in self.session.client.query(
            query, valid_time=valid_time
        ):
            if not finding_type_object:
                logger.warning(
                    "There are %d %s findings but the finding type is not in the database",
                    finding_count,
                    finding_type_name,
                )
                severity = RiskLevelSeverity.PENDING
            else:
                ft = cast(FindingType, self.deserialize(finding_type_object))
                severity = ft.risk_severity or RiskLevelSeverity.PENDING
            severity_counts.update([severity] * finding_count)
        return severity_counts

    def get_bit_configs(self, source: OOI, bit_definition: BitDefinition, valid_time: datetime) -> list[Config]:
        path = Path.parse(f"{bit_definition.config_ooi_relation_path}.<ooi [is Config]")

        query = (
            Query.from_path(path)
            .where(type(source), primary_key=source.primary_key)
            .where(Config, bit_id=bit_definition.id)
        )

        configs = self.query(query, valid_time)

        return [config for config in configs if isinstance(config, Config)]

    def list_related(self, ooi: OOI, path: Path, valid_time: datetime) -> list[OOI]:
        path_start_alias = path.segments[0].source_type
        query = Query.from_path(path).where(path_start_alias, primary_key=ooi.primary_key)

        # query() can return different types depending on the query
        return self.query(query, valid_time)  # type: ignore[return-value]

    def list_findings(
        self,
        severities: set[RiskLevelSeverity],
        valid_time: datetime,
        exclude_muted: bool = False,
        only_muted: bool = False,
        offset: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        search_string: str | None = None,
        order_by: Literal["score", "finding_type"] = "score",
        asc_desc: Literal["asc", "desc"] = "desc",
    ) -> Paginated[Finding]:
        # clause to find risk_severity
        concrete_finding_types = to_concrete({FindingType})
        severity_clauses = [
            f"[?finding_type :{finding_type.get_object_type()}/risk_severity ?severity]"
            for finding_type in concrete_finding_types
        ]
        or_severities = f"(or {' '.join(severity_clauses)})"

        # clause to find risk_score
        score_clauses = [
            f"[?finding_type :{finding_type.get_object_type()}/risk_score ?score]"
            for finding_type in concrete_finding_types
        ]
        or_scores = f"(or {' '.join(score_clauses)})"

        muted_clause = ""
        if exclude_muted:
            muted_clause = "(not-join [?finding] [?muted_finding :MutedFinding/finding ?finding])"
        elif only_muted:
            muted_clause = "[?muted_finding :MutedFinding/finding ?finding]"

        search_statement = (
            f"""[?finding :xt/id ?id]
                                [(clojure.string/includes? ?id \"{escape_string(search_string)}\")]"""
            if search_string
            else ""
        )

        order_statement = f":order-by [[?{order_by} :{asc_desc}]]"

        severity_values = ", ".join([str_val(severity.value) for severity in severities])

        count_query = f"""
            {{
                :query {{
                    :find [(count ?finding)]
                    :in [[severities_ ...]]
                    :where [[?finding :object_type "Finding"]
                            [?finding :Finding/finding_type ?finding_type]
                            {search_statement}
                            [(== ?severity severities_)]
                            {or_severities}
                            {muted_clause}]
                }}
                :in-args [[{severity_values}]]
            }}
        """

        count_results = self.session.client.query(count_query, valid_time)
        count = 0
        if count_results and count_results[0]:
            count = count_results[0][0]

        finding_query = f"""
            {{
                :query {{
                    :find [(pull ?finding [*]) ?score ?finding_type]
                    :in [[severities_ ...]]
                    :where [[?finding :object_type "Finding"]
                            [?finding :Finding/finding_type ?finding_type]
                            [(== ?severity severities_)]
                            {or_severities}
                            {or_scores}
                            {muted_clause}
                            {search_statement}]
                    :limit {limit}
                    :offset {offset}
                    {order_statement}
                }}
               :in-args [[{severity_values}]]
            }}
        """

        return Paginated(count=count, items=[x[0] for x in self.query(finding_query, valid_time)])

    def simplify_keys(self, data: dict[str, Any]) -> dict[str, Any]:
        new_data: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, list):
                new_data[key.split("/")[-1]] = [
                    self.simplify_keys(item) if isinstance(item, dict) else item for item in value
                ]
            elif isinstance(value, dict):
                new_data[key.split("/")[-1]] = self.simplify_keys(value)
            else:
                new_key = key.split("/")[-1] if key.startswith("Report/") else key
                new_data[new_key] = value
        return new_data

    def list_reports(
        self, valid_time: datetime, offset: int, limit: int, recipe_id: UUID | None = None, ignore_count: bool = False
    ) -> Paginated[HydratedReport]:
        date = Aliased(Report, field="date_generated")
        query = Query(Report).where(Report, date_generated=date)

        if recipe_id:
            query = query.where(ReportRecipe, recipe_id=str(recipe_id))
            query = query.where(Report, report_recipe=ReportRecipe)

        if not ignore_count:
            count_results = self.query(query.count(), valid_time)
            count = 0 if not count_results else count_results[0]
        else:
            count = 0

        if settings.asset_reports:
            query = query.pull(Report, fields="[* {:Report/input_oois [*]}]")

        query = query.pull(Report).order_by(date, ascending=False)

        # XTDB requires the field ordered on to be returned in a find statement, see e.g. the discussion here:
        # https://github.com/xtdb/xtdb/issues/418
        results = self.query(query.find(date).limit(limit).offset(offset), valid_time, HydratedReport)

        # Remove the date from the results
        return Paginated(count=count, items=[results[0] for results in results])

    def get_report(self, valid_time: datetime, report_id: str | Reference) -> HydratedReport:
        query = Query(Report).where(Report, primary_key=str(report_id))
        if settings.asset_reports:
            results = self.query(query.pull(Report, fields="[* {:Report/input_oois [*]}]"), valid_time, HydratedReport)
        else:
            results = self.query(query.pull(Report), valid_time, HydratedReport)

        if not results:
            raise ObjectNotFoundException(report_id)

        result = results[0]

        if not isinstance(result, HydratedReport):
            raise ValueError("Invalid query result")

        return result

    def query(
        self, query: str | Query, valid_time: datetime, to_type: type[OOI] | None = None
    ) -> list[OOI | tuple | dict[Any, Any]]:
        """
        Performs the given query and returns the query results at the provided valid_time.

        At this point, the query can return both OOIs or more complex structures, see for example the query-many
        endpoint. For backward compatibility, we try to deserialize oois whenever we expect that to be possible, but
        when we are going to improve and extend query capabilities, deserialization should be moved outside this method.
        """

        results = self.session.client.query(query, valid_time=valid_time)

        parsed_results: list[dict[Any, Any] | OOI | tuple] = []
        for result in results:
            parsed_result = []

            for item in result:
                if isinstance(item, dict):
                    try:
                        parsed_result.append(self.deserialize(item, to_type))
                    except (ValueError, TypeError):
                        parsed_result.append(item)  # type: ignore
                else:
                    parsed_result.append(item)

            if len(parsed_result) == 1:
                parsed_results.append(parsed_result[0])
                continue

            parsed_results.append(tuple(parsed_result))

        return parsed_results
