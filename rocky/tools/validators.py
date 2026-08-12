from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r"^\+?1?\d{11,11}$", message="Phone number must be entered in the format: '+99999999999'. 11 digits allowed."
)
