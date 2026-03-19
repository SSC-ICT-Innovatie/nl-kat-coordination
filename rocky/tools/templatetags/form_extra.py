from django import template

register = template.Library()


@register.filter
def with_form_attr(field, form_id):
    return field.as_widget(attrs={"form": form_id})
