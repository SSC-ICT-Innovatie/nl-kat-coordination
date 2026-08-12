from django import forms
from django.contrib.auth import forms as auth_forms
from django.utils.translation import gettext_lazy as _


class PasswordResetForm(auth_forms.PasswordResetForm):
    email = forms.EmailField(
        label=_("Email address"),
        max_length=254,
        help_text=_("A reset link will be sent to this email"),
        widget=forms.TextInput(attrs={"placeholder": _("The email address connected to your OpenKAT-account")}),
    )
