import json
from datetime import datetime
from typing import Any

from account.models import KATUser
from django import template
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _

from octopoes.models import OOI, Reference, ScanLevel
from octopoes.models.ooi.findings import Finding, FindingType
from tools.view_helpers import get_ooi_url

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_key(array, key):
    return [x[key] for x in array]


@register.filter
def sum_list(array):
    return sum(array)


@register.simple_tag()
def get_scan_levels() -> list[str]:
    return list(map(str, range(1, 5)))


@register.filter
def ooi_types_to_strings(ooi_types: set[type[OOI]]) -> list["str"]:
    return [ooi_type.get_ooi_type() for ooi_type in ooi_types]


@register.filter()
def get_type(x: Any) -> Any:
    return type(x)


@register.simple_tag()
def ooi_url(routename: str, ooi_id: str, organization_code: str, **kwargs: str) -> str:
    return get_ooi_url(routename, ooi_id, organization_code, **kwargs)


@register.filter()
def is_finding(ooi: OOI) -> bool:
    return isinstance(ooi, Finding)


@register.filter()
def is_finding_type(ooi: OOI) -> bool:
    return isinstance(ooi, FindingType)


@register.filter()
def get_type_name(instance):
    return type(instance).__name__


@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    dict_ = context["request"].GET.copy()
    dict_[field] = value
    return dict_.urlencode()


@register.filter
def index(indexable, i):
    return indexable[i]


@register.filter
def pretty_json(obj: dict) -> str:
    return json.dumps(obj, default=str, indent=4)


@register.filter
def human_readable(reference_string: str) -> str:
    return Reference.from_str(reference_string).human_readable


@register.filter
def clearance_level(ooi: OOI) -> ScanLevel:
    if ooi.scan_profile:
        return ooi.scan_profile.level
    else:
        return ScanLevel.L0


@register.filter
def ooi_type(reference_string: str) -> str:
    return Reference.from_str(reference_string).class_


@register.filter
def get_datetime(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str)


@register.filter
def get_first_seen(occurrences: dict) -> datetime:
    first_seen = min(occurrences, key=lambda occurrence: occurrence["first_seen"])["first_seen"]
    return datetime.fromisoformat(first_seen)


@register.filter
def get_user_full_name(ooi: OOI) -> str:
    try:
        return KATUser.objects.get(id=ooi.user_id).get_full_name()
    except ObjectDoesNotExist:
        return _("Unknown user")
