from __future__ import annotations

from enum import Enum, IntEnum
from typing import Any, ClassVar, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, GetCoreSchemaHandler, RootModel
from pydantic_core import CoreSchema, core_schema
from pydantic_core.core_schema import ValidationInfo


class Reference(str):
    @classmethod
    def parse(cls, ref_str: str) -> tuple[str, str]:
        object_type, natural_key_parts = ref_str.split("|", 1)
        return object_type, natural_key_parts

    @property
    def class_(self) -> str:
        return self.parse(self)[0]

    @property
    def natural_key(self) -> str:
        return self.parse(self)[1]

    @property
    def class_type(self) -> type[OOI]:
        from octopoes.models.types import type_by_name

        object_type, _ = self.parse(self)
        return type_by_name(object_type)

    @property
    def tokenized(self) -> PrimaryKeyToken:
        return self.class_type.get_tokenized_primary_key(self.natural_key)

    @property
    def human_readable(self) -> str:
        return self.class_type.format_reference_human_readable(self)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.with_info_after_validator_function(cls.validate, core_schema.str_schema())

    @classmethod
    def validate(cls, v: str, info: ValidationInfo) -> Any:
        if not isinstance(v, str):
            raise TypeError("string required")
        return cls(str(v))

    def __repr__(self) -> str:
        return f"Reference({super().__repr__()})"

    @classmethod
    def from_str(cls, ref_str: str) -> Reference:
        return cls(ref_str)


class ScanLevel(IntEnum):
    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4

    def __str__(self) -> str:
        return str(self.value)


class ScanProfileType(Enum):
    DECLARED = "declared"
    INHERITED = "inherited"
    EMPTY = "empty"


class ScanProfileBase(BaseModel):
    scan_profile_type: str
    reference: Reference
    level: ScanLevel
    user_id: int | None = None

    def __eq__(self, other):
        if isinstance(other, ScanProfileBase) and self.__class__ == other.__class__:
            return self.reference == other.reference and self.level == other.level
        return False

    def __hash__(self):
        return hash(self.reference)

    @property
    def human_readable(self) -> str:
        return f"L{self.level}"


class EmptyScanProfile(ScanProfileBase):
    scan_profile_type: Literal["empty"] = ScanProfileType.EMPTY.value
    level: ScanLevel = ScanLevel.L0


class DeclaredScanProfile(ScanProfileBase):
    scan_profile_type: Literal["declared"] = ScanProfileType.DECLARED.value


class InheritedScanProfile(ScanProfileBase):
    scan_profile_type: Literal["inherited"] = ScanProfileType.INHERITED.value


ScanProfile = EmptyScanProfile | InheritedScanProfile | DeclaredScanProfile


class OOI(BaseModel):
    object_type: str

    scan_profile: ScanProfile | None = None
    user_id: int | None = None

    _natural_key_attrs: ClassVar[list[str]] = []
    _reverse_relation_names: ClassVar[dict[str, str]] = {}
    _information_value: ClassVar[list[str]] = []
    _traversable: ClassVar[bool] = True

    primary_key: str = ""

    def model_post_init(self, __context: Any) -> None:  # noqa: F841
        self.primary_key = self.primary_key or f"{self.get_object_type()}|{self.natural_key}"

    def __str__(self) -> str:
        return self.primary_key

    @classmethod
    def get_object_type(cls) -> str:
        return cls.__name__

    @classmethod
    def strict_subclasses(cls) -> list[type[OOI]]:
        """FastAPI creates duplicate class instances when parsing return types."""

        return [subclass for subclass in cls.__subclasses__() if subclass.__name__ != cls.__name__]

    # FIXME: Legacy usage in Rocky/Boefjes
    @classmethod
    def get_ooi_type(cls) -> str:
        return cls.get_object_type()

    # FIXME: Legacy usage in Rocky/Boefjes
    @property
    def ooi_type(self) -> str:
        return self.get_object_type()

    @property
    def human_readable(self) -> str:
        return self.format_reference_human_readable(self.reference)

    @property
    def natural_key(self) -> str:
        parts = []

        for attr in self._natural_key_attrs:
            part = getattr(self, attr)
            if part is None:
                part = ""
            if isinstance(part, Reference):
                part = part.natural_key
            elif isinstance(part, Enum):
                part = str(part.value)
            else:
                part = str(part)

            parts.append(part)

        return "|".join(parts)

    def get_information_id(self) -> str:
        def format_attr(value_: Any) -> str:
            if isinstance(value_, Enum):
                return value_.value
            return value_

        parts = [self.__class__.__name__]
        for attr in self._information_value:
            value = self.__getattribute__(attr)
            parts.append(format_attr(value))
        return "|".join(map(str, parts))

    @property
    def reference(self) -> Reference:
        return Reference(self.primary_key)

    @classmethod
    def get_reverse_relation_name(cls, attr: str) -> str:
        return cls._reverse_relation_names.get(attr, f"{cls.get_object_type()}_{attr}")

    @classmethod
    def get_tokenized_primary_key(cls, natural_key: str) -> PrimaryKeyToken:
        token_tree = build_token_tree(cls)
        natural_key_parts = natural_key.split("|")

        def hydrate(node: dict[str, dict | str]) -> dict | str:
            for key, value in node.items():
                if isinstance(value, dict):
                    node[key] = hydrate(value)
                else:
                    node[key] = natural_key_parts.pop(0) if natural_key_parts else value
            return node

        return PrimaryKeyToken.model_validate(hydrate(token_tree))

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return str(reference)

    @classmethod
    def traversable(cls) -> bool:
        return cls._traversable

    def serialize(self) -> SerializedOOI:
        serialized_oois = {}
        model_fields = self.__class__.model_fields
        for key, value in self:
            if key not in model_fields:
                continue
            serialized_oois[key] = self._serialize_value(value, model_fields[key].is_required())
        return serialized_oois

    def _serialize_value(self, value: Any, required: bool) -> SerializedOOIValue:
        if isinstance(value, list):
            return [self._serialize_value(item, required) for item in value]
        if isinstance(value, Reference):
            try:
                return value.tokenized.root
            except AttributeError:
                if required:
                    raise

                return None
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, int | float):
            return value
        return str(value)

    def __hash__(self) -> int:
        return hash(self.primary_key)


OOIClassType = TypeVar("OOIClassType")


def format_id_short(id_: str) -> str:
    """Format the id in a short way. > 33 characters, interpolate with ..."""
    if len(id_) > 33:
        return f"{id_[:15]}...{id_[-15:]}"
    return id_


class PrimaryKeyToken(RootModel):
    root: dict[str, str | PrimaryKeyToken]

    def __getattr__(self, item: str) -> Any:
        return self.root[item]

    def __getitem__(self, item: str) -> Any:
        return self.root[item]


PrimaryKeyToken.model_rebuild()


def get_leaf_subclasses(cls: type[OOI]) -> set[type[OOI]]:
    if not cls.strict_subclasses():
        return {cls}
    child_sets = [get_leaf_subclasses(child_cls) for child_cls in cls.strict_subclasses()]
    return set().union(*child_sets)


def build_token_tree(ooi_class: type[OOI]) -> dict[str, dict | str]:
    tokens: dict[str, dict | str] = {}

    for attribute in ooi_class._natural_key_attrs:
        field = ooi_class.model_fields[attribute]

        if field.annotation in (Reference, Reference | None):
            from octopoes.models.types import related_object_type

            related_class = related_object_type(field)
            trees = [build_token_tree(related_class) for related_class in get_leaf_subclasses(related_class)]

            # combine trees
            tokens[attribute] = {key: value_ for tree in trees for key, value_ in tree.items()}
        else:
            tokens[attribute] = field.default
    return tokens


SerializedOOIValue: TypeAlias = None | str | int | float | dict[str, str | PrimaryKeyToken] | list["SerializedOOIValue"]
SerializedOOI: TypeAlias = dict[str, SerializedOOIValue]
