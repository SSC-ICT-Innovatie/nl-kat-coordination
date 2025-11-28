from typing import Any

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.simple_tag()
def get_scan_levels() -> list[str]:
    return list(map(str, range(1, 5)))


@register.filter()
def get_type(x: Any) -> Any:
    return type(x).__name__


@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    dict_ = context["request"].GET.copy()
    dict_[field] = value
    return dict_.urlencode()


@register.filter
def index(indexable, i):
    return indexable[i]


@register.filter
def with_form_attr(field, form_id):
    return field.as_widget(attrs={"form": form_id})


@register.filter
def to_class_name(model: object) -> str:
    return model.__class__.__name__
