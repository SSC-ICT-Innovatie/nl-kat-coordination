from account.validators import get_password_validators_help_texts
from django.test import override_settings


@override_settings(
    AUTH_PASSWORD_VALIDATORS=[
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}}
    ]
)
def test_password_validators_help_texts_default():
    help_text = get_password_validators_help_texts()
    assert "12 characters" in help_text
    assert "letters" not in help_text


@override_settings(
    AUTH_PASSWORD_VALIDATORS=[
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
        {
            "NAME": "django_password_validators.password_character_requirements"
            ".password_validation.PasswordCharacterValidator",
            "OPTIONS": {
                "min_length_digit": 2,
                "min_length_alpha": 5,
                "min_length_special": 9,
                "min_length_lower": 4,
                "min_length_upper": 7,
                "special_characters": "~!@#$%^&",
            },
        },
    ]
)
def test_password_validators_help_texts_all_options():
    help_text = get_password_validators_help_texts()

    assert "12 characters" in help_text
    assert "2 digits" in help_text
    assert "5 letters" in help_text
    assert "9 special characters such as: ~!@#$%^&" in help_text
    assert "4 lower case letters" in help_text
    assert "7 upper case letters" in help_text
