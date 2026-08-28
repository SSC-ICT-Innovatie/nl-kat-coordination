import re
from collections.abc import Iterable, Mapping
from typing import Any

from octopoes.xtdb import FieldSet
from octopoes.xtdb.related_field_generator import RelatedFieldNode


def join_csv(values: Iterable[Any]) -> str:
    return " ".join(values)


def str_val(val):
    if isinstance(val, str):
        val = edn_escape(val)
        return f'"{val}"'
    return val


def edn_escape(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\b", "\\b")
        .replace("\f", "\\f")
    )


def generate_pull_query(
    field_set: FieldSet = FieldSet.ALL_FIELDS,
    where: Mapping[str, str | int | list[str] | list[int] | set[str] | set[int]] | None = None,
    offset: int | None = None,
    limit: int | None = None,
    field_node: RelatedFieldNode | None = None,
) -> str:
    pk_prefix = ":xt/id"

    in_params = []
    in_args = []
    where_mapping = {}
    # Where default
    if where is None:
        where = {}
    # Break where clause in relevant sections
    for key, value in where.items():
        var_name = re.sub("[^0-9a-zA-Z]+", "_", key)
        if isinstance(value, list | set):
            value = sorted([str_val(value) for value in value])
            _csv = join_csv(value)
            in_args.append(f"[{_csv}]")
            in_params.append(f"[_{var_name} ...]")
        else:
            in_args.append(str_val(value))
            in_params.append(f"_{var_name}")
        where_mapping[key] = f"_{var_name}"

    # Fields default
    if field_node is not None:
        q_fields = field_node.generate_field(field_set, pk_prefix)
    else:
        q_fields = pk_prefix if field_set is FieldSet.ONLY_ID else "*"
        q_fields = f"[{q_fields}]"
    q_fields = f"[(pull ?e {q_fields})]"

    q_limit = ""
    if limit is not None:
        q_limit = f":limit {limit}" if limit is not None else ""

    q_offset = ""
    if offset is not None:
        q_offset = f":offset {offset}" if offset is not None else ""

    q_in = ""
    if in_params:
        q_in = f":in [{' '.join(in_params)}]"

    if not where_mapping:
        where_mapping = {pk_prefix: ""}
    where_clauses = [f"[?e :{key} {val}]" for key, val in where_mapping.items()]
    q_where = f":where [{' '.join(where_clauses)}]"

    q_in_args = ""
    if in_args:
        s = " ".join(map(str, in_args))
        q_in_args = f":in-args [ {s} ]"

    find_section = " ".join([q_fields, q_in, q_where, q_offset, q_limit])

    return f"{{:query {{:find {find_section} }} {q_in_args}}}"
