import inspect
from typing import Any

from pydantic import Field
from pydantic.fields import FieldInfo

from octopoes.models import OOI

# Dynamically determine allowed Field() keyword parameters
_FIELD_SIGNATURE = inspect.signature(Field)
_ALLOWED_FIELD_KWARGS = {
    name
    for name, param in _FIELD_SIGNATURE.parameters.items()
    if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
}


def ReferenceField(
    object_type: str | type[OOI],
    *,
    max_issue_scan_level: int | None = None,
    max_inherit_scan_level: int | None = None,
    **kwargs: Any,
) -> FieldInfo:
    if not isinstance(object_type, str):
        object_type = object_type.get_object_type()

    field_kwargs: dict[str, Any] = {}

    # Start with caller-provided json_schema_extra if present
    json_schema_extra = dict(kwargs.pop("json_schema_extra", {}) or {})

    # Always inject your metadata
    json_schema_extra["object_type"] = object_type

    if max_issue_scan_level is not None:
        json_schema_extra["max_issue_scan_level"] = max_issue_scan_level

    if max_inherit_scan_level is not None:
        json_schema_extra["max_inherit_scan_level"] = max_inherit_scan_level

    for key, value in kwargs.items():
        if key in _ALLOWED_FIELD_KWARGS:
            field_kwargs[key] = value
        elif value is not None:
            json_schema_extra[key] = value

    return Field(**field_kwargs, json_schema_extra=json_schema_extra)
