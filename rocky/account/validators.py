from django.conf import settings
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _


def get_password_validators_help_texts():
    """
    Set password help_texts especially for Manon.
    """
    help_texts = []
    validators = {}
    explanation = _("Your password must contain at least the following but longer passwords are recommended:")
    for validator in settings.AUTH_PASSWORD_VALIDATORS:
        validators.update(validator["OPTIONS"])

    # Get possible password restrictions and update help text.
    # Because restriction not always set, determine if restriction is set before adding to help text.
    min_length = str(validators.get("min_length", ""))
    if min_length:
        min_length += _(" characters")
    min_length_digit = str(validators.get("min_length_digit", ""))
    if min_length_digit:
        min_length_digit += _(" digits")
    min_length_alpha = str(validators.get("min_length_alpha", ""))
    if min_length_alpha:
        min_length_alpha += _(" letters")
    min_length_special = str(validators.get("min_length_special", ""))
    if min_length_special:
        min_length_special += _(f" special characters such as: {str(validators.get('special_characters',''))}")
    min_length_lower = str(validators.get("min_length_lower", ""))
    if min_length_lower:
        min_length_lower += _(" lower case letters")
    min_length_upper = str(validators.get("min_length_upper", ""))
    if min_length_upper:
        min_length_upper += _(" upper case letters")
    extra_information = format_html(
        "For more information on making a secure password, see: "
        "<a target='_blank' href='https://veiliginternetten.nl/mijn-wachtwoord-123456/'>"
        "Veilig internetten - Wat is een sterk wachtwoord?</a>"
    )
    help_texts += [
        min_length,
        min_length_digit,
        min_length_alpha,
        min_length_special,
        min_length_lower,
        min_length_upper,
        extra_information,
    ]
    # Remove empty strings, because they are not set.
    help_texts = [help_text for help_text in help_texts if help_text]
    help_text_builder = format_html_join("", "<li>{}</li>", ((help_text,) for help_text in help_texts))
    return format_html("<p>{}</p><ul>{}</ul>", explanation, help_text_builder) if help_text_builder else ""
