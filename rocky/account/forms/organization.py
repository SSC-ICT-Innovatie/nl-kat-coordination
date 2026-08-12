from django import forms
from django.utils.translation import gettext_lazy as _
from tools.forms.settings import BLANK_CHOICE
from tools.models import Organization

from account.models import KATUser


class OrganizationListForm(forms.Form):
    """
    Creates a dropdown list of Organizations of a particular member.
    """

    error_messages = {"required": _("Organization is required.")}

    def __init__(self, user: KATUser, exclude_organization: Organization, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organizations = [
            [organization.code, organization.name]
            for organization in user.organizations
            if organization != exclude_organization
        ]

        if organizations:
            self.fields["organization"] = forms.ChoiceField(
                required=True,
                label=_("Organizations"),
                help_text=_("The organization from which to clone settings."),
                error_messages=self.error_messages,
            )

            self.fields["organization"].choices = [BLANK_CHOICE] + organizations
