from django import template

from rocky.views.mixins import FINDING_LIST_COLUMNS, OBJECT_LIST_COLUMNS

register = template.Library()


@register.filter
def get_column_name_finding_list(column_value: str) -> str:
    return FINDING_LIST_COLUMNS.get(column_value, "")


@register.filter
def get_column_name_object_list(column_value: str) -> str:
    return OBJECT_LIST_COLUMNS.get(column_value, "")
