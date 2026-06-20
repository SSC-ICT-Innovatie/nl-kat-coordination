from django import template

register = template.Library()


@register.filter
def is_multiple_hidden(field):
    value = field.value()
    return isinstance(value, list | tuple)


@register.filter
def get_item(dictionary: dict, key):
    return dictionary.get(key)
