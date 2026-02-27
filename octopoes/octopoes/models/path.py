from __future__ import annotations

from enum import Enum
from functools import cache

from pyparsing import Literal, Opt, ParseException, Word, alphas

from octopoes.models import OOI
from octopoes.models.types import (
    OOITYPE_BY_NAME,
    OOIType,
    get_concrete_types,
    get_relation,
    get_relations,
    to_concrete,
    type_by_name,
)

type_intersection_grammar = Literal("[") + "is" + Word(alphas) + "]"

incoming_step_grammar = "<" + Word(alphas + "_") + type_intersection_grammar
outgoing_step_grammar = Word(alphas + "_") + Opt(type_intersection_grammar)


class Direction(Enum):
    OUTGOING = 0
    INCOMING = 1


class Segment:
    def __init__(self, source_type: type[OOI], direction: Direction, property_name: str, target_type: type[OOI] | None):
        self.source_type = source_type
        self.direction = direction
        self.property_name = property_name
        self.target_type = target_type

    def __hash__(self):
        """Hashing for cache usage"""
        return hash("".join((str(self.source_type), str(self.direction), self.property_name, str(self.target_type))))

    @classmethod
    def parse_step(cls, step: str) -> tuple[Direction, str, type[OOIType] | None]:
        try:
            parsed_step = incoming_step_grammar.parse_string(step)
            incoming, property_name, _, _, target_type, _ = parsed_step
            return Direction.INCOMING, property_name, type_by_name(target_type)
        except ParseException:
            try:
                parsed_step = outgoing_step_grammar.parse_string(step)
                if len(parsed_step) == 1:
                    return Direction.OUTGOING, parsed_step[0], None
                property_name, _, _, target_type, _ = parsed_step
                return Direction.OUTGOING, property_name, type_by_name(target_type)
            except ParseException:
                raise ValueError(f"Could not parse step: {step}")

    @classmethod
    def calculate_step(cls, source_type: type[OOI], step: str) -> Segment:
        direction, property_name, explicit_target_type = cls.parse_step(step)

        if explicit_target_type:
            return cls(source_type, direction, property_name, explicit_target_type)

        try:
            return cls(source_type, direction, property_name, get_relation(source_type, property_name))
        except KeyError:
            for concrete in source_type.strict_subclasses():
                try:
                    return cls(source_type, direction, property_name, get_relation(concrete, property_name))
                except KeyError:
                    pass

            # We failed to get the relation, so the target in the step is not a relation but a regular field of the OOI.
            return cls(source_type, direction, property_name, None)

    def reverse(self) -> Segment:
        if self.target_type is None:
            raise ValueError("Cannot reverse segment without a target type.")

        return self.__class__(
            self.target_type,
            Direction.OUTGOING if self.direction == Direction.INCOMING else Direction.INCOMING,
            self.property_name,
            self.source_type,
        )

    def encode(self) -> str:
        if self.direction == Direction.OUTGOING:
            return f"{self.source_type.get_object_type()}/{self.property_name}"
        else:
            if self.target_type is None:
                raise ValueError("Direction cannot be incoming if target type is None")

            return f"{self.target_type.get_object_type()}/_{self.property_name}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Segment):
            return NotImplemented

        return (
            self.source_type == other.source_type
            and self.direction == other.direction
            and self.property_name == other.property_name
            and self.target_type == other.target_type
        )

    def __str__(self) -> str:
        if self.direction == Direction.INCOMING:
            if self.target_type is None:
                raise ValueError("Direction cannot be incoming if target type is None")

            return f"<{self.property_name}[is {self.target_type.get_object_type()}]"
        else:
            return f"{self.property_name}"

    def __repr__(self) -> str:
        return str(self)


class Path:
    def __init__(self, segments: list[Segment]):
        self.segments = segments

    @classmethod
    def parse(cls, path: str) -> Path:
        start_type, step, *rest = path.split(".")

        segments = [Segment.calculate_step(type_by_name(start_type), step)]
        for next_step in rest:
            if segments[-1].target_type is None:
                break
            segments.append(Segment.calculate_step(segments[-1].target_type, next_step))

        return Path(segments)

    def reverse(self) -> Path:
        # TODO: we fail if the last segment is a regular field. Another option is stripping it from the reversed path?
        return Path([segment.reverse() for segment in reversed(self.segments)])

    def __str__(self) -> str:
        start_type = self.segments[0].source_type.get_object_type()
        segments = ".".join(map(str, self.segments))
        return f"{start_type}.{segments}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Path | str):
            return NotImplemented

        return str(self) == str(other)

    def __lt__(self, other):
        return str(self) < str(other)

    def __hash__(self):
        return hash(str(self))

    def __repr__(self) -> str:
        return str(self)


def get_paths_to_neighbours(source_type: type[OOI]) -> set[Path]:
    """
    Public API: safely caches paths using string keys.
    """
    return _cached_paths_to_neighbours(source_type.__name__)


@cache
def _cached_paths_to_neighbours(cls_name: str) -> set[Path]:
    """
    Internal cached function. Only takes hashable arguments (str).
    """
    source_type = OOITYPE_BY_NAME[cls_name]  # resolve class from name
    relation_paths: set[Path] = set()

    # OUTGOING paths from source_type
    for property_name, related_type in get_relations(source_type).items():
        relation_paths.add(Path([Segment(source_type, Direction.OUTGOING, property_name, related_type)]))

    # INCOMING paths from all concrete types pointing to source_type
    for other_type in get_concrete_types():
        for property_name, related_type in get_relations(other_type).items():
            if source_type in to_concrete({related_type}):
                relation_paths.add(Path([Segment(source_type, Direction.INCOMING, property_name, other_type)]))

    return relation_paths


@cache
def get_max_scan_level_inheritance(segment: Segment) -> int | None:
    """This does not change during runtime as the models are static and as such can be cached."""
    if segment.direction == Direction.INCOMING:
        if segment.target_type is None:
            raise ValueError("Direction cannot be incoming if target type is None")

        return segment.target_type.model_fields[segment.property_name].json_schema_extra.get(
            "max_issue_scan_level", None
        )
    else:
        return segment.source_type.model_fields[segment.property_name].json_schema_extra.get(
            "max_inherit_scan_level", None
        )


@cache
def get_max_scan_level_issuance(segment: Segment) -> int | None:
    """This does not change during runtime as the models are static and as such can be cached."""
    if segment.direction == Direction.INCOMING:
        if segment.target_type is None:
            raise ValueError("Direction cannot be incoming if target type is None")

        return segment.target_type.model_fields[segment.property_name].json_schema_extra.get(
            "max_inherit_scan_level", None
        )
    else:
        return segment.source_type.model_fields[segment.property_name].json_schema_extra.get(
            "max_issue_scan_level", None
        )
