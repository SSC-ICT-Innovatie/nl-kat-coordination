from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

from octopoes.models import OOI
from octopoes.models.path import Direction, Path
from octopoes.models.types import get_abstract_types, to_concrete


class InvalidField(ValueError):
    pass


class InvalidPath(ValueError):
    pass


@dataclass(frozen=True)
class Aliased:
    """OOI type wrapper to have control over the query alias used per type. This is necessary to traverse the same
    OOI type more than once, since by default we have that
        >>> Query(DNSAAAARecord)
        >>>     .where(DNSAAAARecord, hostname=Hostname)
        >>>     .where(Hostname, primary_key="Hostname|internet|test.com")
        >>>     .where(DNSNSRecord, hostname=Hostname)
        >>>     .where(DNSNSRecord, name_server_hostname=Hostname)
    needs the same Hostname to be both the DNSNSRecord.hostname and the DNSNSRecord.name_server_hostname.

    But if we use
        >>> hostname = Aliased(Hostname)
        >>> Query(DNSAAAARecord)
        >>>     .where(DNSAAAARecord, hostname=hostname)
        >>>     .where(DNSNSRecord, name_server_hostname=hostname)
        >>>     .where(DNSNSRecord, hostname=Hostname)
        >>>     .where(Hostname, primary_key="Hostname|internet|test.com")
    we will get the DNSAAAARecords of the Hostname of the name server of "test.com".
    """

    type: type[OOI] = OOI  # Represents a generic lookup on all OOIs

    # The lambda makes it possible to mock the factory more easily, see:
    # https://stackoverflow.com/questions/61257658/python-dataclasses-mocking-the-default-factory-in-a-frozen-dataclass
    alias: UUID = field(default_factory=lambda: uuid4())

    # Sometimes an Alias refers to a plain field, not a whole model. The current solution is suboptimal
    # as you can use aliases freely in Datalog but are now tied to the OOI types too much. TODO!
    field: str | None = field(default=None)


Ref = type[OOI] | Aliased


@dataclass(frozen=True)
class Query:
    """Object representing an XTDB query.

        result_type: The OOI Type being queried: executing the query should yield only this OOI Type.

    Example usage:

    >>> query = Query(Network).where(Network, name="test")
    >>> query = query.where(Finding, ooi=Network)
    >>> query.format()
    '
    {:query {:find [(pull Network [*])] :where [
        [ Network :Network/name "test" ]
        [ Finding :Finding/ooi Network ]
    ]}}
    '
    """

    result_type: Ref = OOI

    _where_clauses: list[str] = field(default_factory=list)
    _find_clauses: list[str] = field(default_factory=list)
    _limit: int | None = None
    _offset: int | None = None
    _order_by: tuple[Aliased, bool] | None = None

    def where(self, ooi_type: Ref, **kwargs) -> Query:
        new = self._copy()

        for field_name, value in kwargs.items():
            new._where_field_is(ooi_type, field_name, value)

        return new

    def where_in(self, ooi_type: Ref, **kwargs: Iterable[str]) -> Query:
        """Allows for filtering on multiple values for a specific field."""
        new = self._copy()

        for field_name, values in kwargs.items():
            new._where_field_in(ooi_type, field_name, values)

        return new

    def format(self) -> str:
        new = self._copy()

        return new._compile(separator="\n    ")

    @classmethod
    def from_path(cls, path: Path) -> Query:
        """
        Create a query from a Path.

        The last segment in the path is assumed to be the queries OOI Type. Because paths often describe type traversal,
        we assume that every time we get a duplicate type, we have to alias it, except the target type.

        If the last segment is not an OOI Type, the result of the query changes to the value of that specific field
        instead of returning the complete OOIs for the last type.
        """

        ooi_type = (
            path.segments[-1].target_type
            if path.segments[-1].target_type is not None
            else path.segments[-1].source_type
        )

        query = cls(ooi_type)
        target_ref: Ref = path.segments[0].source_type
        alias_map: dict[str, Ref] = {}

        if not path.segments:
            return query

        for segment in path.segments:
            source_ref = alias_map.get(segment.source_type.get_object_type(), segment.source_type)

            if segment.source_type.get_object_type() not in alias_map:  # Only happens on the first segment
                alias_map[segment.source_type.get_object_type()] = source_ref

            if segment.target_type is None:
                # The last segment is a regular field, so we query for that field value
                field_alias = Aliased(ooi_type, field=segment.property_name)
                query = query.where(source_ref, **{segment.property_name: field_alias}).find(field_alias)
                break

            if segment.target_type.get_object_type() not in alias_map:
                target_ref = segment.target_type
                alias_map[segment.target_type.get_object_type()] = target_ref
            else:
                target_ref = Aliased(segment.target_type)
                alias_map[segment.target_type.get_object_type()] = target_ref

            if segment.direction is Direction.OUTGOING:
                query = query.where(source_ref, **{segment.property_name: target_ref})
            else:
                query = query.where(target_ref, **{segment.property_name: source_ref})

        # Make sure we use the last reference in the path as a target
        query = replace(query, result_type=target_ref)

        return query

    def pull(self, ooi_type: Ref, *, fields: str = "[*]") -> Query:
        """By default, we pull the target type. But when using find, count, etc., you have to pull explicitly."""
        new = self._copy()

        new._find_clauses.append(f"(pull {new._get_object_alias(ooi_type)} {fields})")

        return new

    def find(self, item: Ref, *, index: int | None = None) -> Query:
        """Add a find clause, so we can select specific fields in a query to be returned as well."""
        if index is None:
            return replace(self, _find_clauses=self._find_clauses + [self._get_object_alias(item)])
        else:
            find_clauses = self._find_clauses
            find_clauses.insert(index, self._get_object_alias(item))
            return replace(self, _find_clauses=find_clauses)

    def count(self, ooi_type: Ref | None = None) -> Query:
        if ooi_type:
            return replace(self, _find_clauses=self._find_clauses + [f"(count {self._get_object_alias(ooi_type)})"])
        else:
            return replace(
                self, _find_clauses=self._find_clauses + [f"(count {self._get_object_alias(self.result_type)})"]
            )

    def limit(self, limit: int) -> Query:
        return replace(self, _limit=limit)

    def offset(self, offset: int) -> Query:
        return replace(self, _offset=offset)

    def order_by(self, ref: Aliased, ascending: bool = True) -> Query:
        return replace(self, _order_by=(ref, ascending))

    def _copy(self) -> Query:
        return replace(self)

    def _where_field_is(self, ref: Ref, field_name: str, value: Ref | str | set[str] | bool) -> None:
        """
        We need isinstance(value, type) checks to verify value is an OOIType, as issubclass() fails on non-classes:

            >>> value = Network
            >>> isinstance(value, OOIType)
            False
            >>> isinstance(value, OOI)
            False
            >>> isinstance(value, type)
            True
            >>> issubclass(value, OOI)
            True
            >>> issubclass(3, OOI)
            Traceback (most recent call last):
              [...]
            TypeError: issubclass() arg 1 must be a class
        """
        ooi_type = ref.type if isinstance(ref, Aliased) else ref
        abstract_types = get_abstract_types()

        if (
            field_name not in ooi_type.model_fields
            and field_name != "id"
            and (
                ooi_type not in abstract_types
                or not any(field_name in concrete_type.model_fields for concrete_type in ooi_type.strict_subclasses())
            )
        ):
            raise InvalidField(f'"{field_name}" is not a field of {ooi_type.get_object_type()}')

        if isinstance(value, str):
            value = value.replace("\\", "\\\\")
            value = value.replace('"', r"\"")

        if ooi_type in abstract_types and ooi_type != OOI:
            if isinstance(value, str):
                self._add_or_statement_for_abstract_types(ref, field_name, f'"{value}"')
                return

            if isinstance(value, bool):
                self._add_or_statement_for_abstract_types(ref, field_name, str(value).lower())
                return

            if not isinstance(value, type | Aliased):
                raise InvalidField(f"value '{value}' for abstract class fields should be a string or an OOI Type")

            if isinstance(value, Aliased) or issubclass(value, OOI):
                self._add_or_statement_for_abstract_types(ref, field_name, self._get_object_alias(value))
                return

        if isinstance(value, str):
            self._add_where_statement(ref, field_name, f'"{value}"')
            return

        if isinstance(value, bool):
            self._add_where_statement(ref, field_name, str(value).lower())
            return

        if not isinstance(value, type | Aliased):
            raise InvalidField(f"value '{value}' should be a string or an OOI Type")

        if not isinstance(value, Aliased) and not issubclass(value, OOI):
            raise InvalidField(f"{value} is not an OOI")

        self._add_where_statement(ref, field_name, self._get_object_alias(value))

    def _where_field_in(self, ref: Ref, field_name: str, values: Iterable[str]) -> None:
        ooi_type = ref.type if isinstance(ref, Aliased) else ref

        if field_name not in ooi_type.model_fields and field_name != "id":
            raise InvalidField(f'"{field_name}" is not a field of {ooi_type.get_object_type()}')

        new_values = []
        for value in values:
            if not isinstance(value, str):
                raise InvalidField("Only strings allowed as values for a WHERE IN statement for now.")

            value = value.replace("\\", "\\\\")
            value = value.replace('"', r"\"")
            new_values.append(f'"{value}"')

        if ooi_type in get_abstract_types() and ooi_type != OOI:
            types_to_check = ooi_type.strict_subclasses()
        else:
            types_to_check = [ooi_type]

        self._where_clauses.append(
            self._or_statement_for_multiple_values(self._get_object_alias(ref), types_to_check, field_name, new_values)
        )

    def _add_where_statement(self, ref: Ref, field_name: str, to_alias: str) -> None:
        ooi_type = ref.type if isinstance(ref, Aliased) else ref

        if ooi_type != OOI:
            self._where_clauses.append(self._assert_type(ref, ooi_type))

        if field_name == "id":
            self._where_clauses.append(self._relationship(self._get_object_alias(ref), "xt", field_name, to_alias))
        else:
            self._where_clauses.append(
                self._relationship(self._get_object_alias(ref), ooi_type.get_object_type(), field_name, to_alias)
            )

    def _add_or_statement_for_abstract_types(self, ref: Ref, field_name: str, to_alias: str) -> None:
        ooi_type = ref.type if isinstance(ref, Aliased) else ref

        if ooi_type != OOI:
            self._where_clauses.append(self._assert_type(ref, ooi_type))
        self._where_clauses.append(
            self._or_statement_for_abstract_types(
                self._get_object_alias(ref), ooi_type.strict_subclasses(), field_name, to_alias
            )
        )

    def _or_statement_for_abstract_types(
        self, from_alias: str, concrete_types: list[type[OOI]], field_name: str, to_alias: str
    ) -> str:
        relationships = [
            self._relationship(from_alias, concrete_type.get_object_type(), field_name, to_alias)
            for concrete_type in concrete_types
        ]

        return f"(or {' '.join(relationships)} )"

    def _or_statement_for_multiple_values(
        self, from_alias: str, ooi_types: list[type[OOI]], field_name: str, to_aliases: list[str]
    ) -> str:
        if field_name == "id":  # Generic field for XTDB entities. TODO: refactor
            relationships = [self._relationship(from_alias, "xt", "id", to_alias) for to_alias in to_aliases]
        else:
            relationships = [
                self._relationship(from_alias, ooi_type.get_object_type(), field_name, to_alias)
                for to_alias in to_aliases
                for ooi_type in ooi_types
            ]

        return f"(or {' '.join(relationships)} )"

    def _relationship(self, from_alias: str, field_type: str, field_name: str, to_alias: str) -> str:
        return f"[ {from_alias} :{field_type}/{field_name} {to_alias} ]"

    def _assert_type(self, ref: Ref, ooi_type: type[OOI]) -> str:
        if ooi_type not in get_abstract_types():
            return self._to_object_type_statement(ref, ooi_type)

        concrete = sorted(to_concrete({ooi_type}), key=lambda t: t.__name__)
        return f"(or {' '.join([self._to_object_type_statement(ref, x) for x in concrete])} )"

    def _to_object_type_statement(self, ref: Ref, other_type: type[OOI]) -> str:
        return f'[ {self._get_object_alias(ref)} :object_type "{other_type.get_object_type()}" ]'

    def _compile_where_clauses(self, *, separator: str = " ") -> str:
        """Sorted and deduplicated where clauses, since they are both idempotent and commutative"""

        return separator + separator.join(sorted(set(self._where_clauses)))

    def _compile_find_clauses(self) -> str:
        return " ".join(self._find_clauses)

    def _compile(self, *, separator: str = " ") -> str:
        result_ooi_type = self.result_type.type if isinstance(self.result_type, Aliased) else self.result_type

        if result_ooi_type != OOI:
            self._where_clauses.append(self._assert_type(self.result_type, result_ooi_type))

        if not self._find_clauses:
            new = replace(
                self, _find_clauses=self._find_clauses + [f"(pull {self._get_object_alias(self.result_type)} [*])"]
            )
        else:
            new = self

        where_clauses = new._compile_where_clauses(separator=separator)
        find_clauses = new._compile_find_clauses()
        compiled = f"{{:query {{:find [{find_clauses}] :where [{where_clauses}]"

        if new._order_by is not None:
            asc_desc = ":asc" if new._order_by[1] else ":desc"
            compiled += f" :order-by [[{new._get_object_alias(new._order_by[0])} {asc_desc}]]"

        if new._limit is not None:
            compiled += f" :limit {new._limit}"

        if new._offset is not None:
            compiled += f" :offset {new._offset}"

        return compiled + "}}"

    def _get_object_alias(self, object_type: Ref) -> str:
        if isinstance(object_type, Aliased):
            base = "?" + str(object_type.alias)

            # To have at least a way to separate aliases for types and plain fields in the raw query
            return base if not object_type.field else base + "?" + object_type.field

        return object_type.get_object_type()

    def __str__(self) -> str:
        return self._compile()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Query):
            return NotImplemented

        return str(self) == str(other)
