import csv
import io
from typing import Any

import structlog
from account.forms import AccountTypeSelectForm, MemberRegistrationForm, PasswordResetForm
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.forms import Form
from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import FormView
from onboarding.view_helpers import DNS_REPORT_LEAST_CLEARANCE_LEVEL
from tools.forms.upload_csv import UploadCSVForm
from tools.models import GROUP_ADMIN, GROUP_CLIENT, GROUP_REDTEAM, OrganizationMember
from tools.view_helpers import Breadcrumb, OrganizationMemberBreadcrumbsMixin

from rocky.messaging import clearance_level_warning_dns_report

logger = structlog.get_logger(__name__)

User = get_user_model()


MEMBER_UPLOAD_COLUMNS = [
    "full_name",
    "email",
    "account_type",
    "trusted_clearance_level",
    "acknowledged_clearance_level",
]
CSV_CRITERIA = [
    _("Add column titles, followed by each object on a new line."),
    _("The columns are: ") + ",".join(f"'{column}'" for column in MEMBER_UPLOAD_COLUMNS),
    _("Clearance levels should be between -1 and 4."),
    _("Account type can be one of: ") + f"'{GROUP_CLIENT}', '{GROUP_ADMIN}' and '{GROUP_REDTEAM}'",
]


class OrganizationMemberAddAccountTypeView(
    OrganizationPermissionRequiredMixin, OrganizationMemberBreadcrumbsMixin, OrganizationView, FormView
):
    """
    View to create a new member. Step 1: choose an account type.
    """

    template_name = "organizations/organization_member_add_account_type.html"
    permission_required = "tools.add_organizationmember"
    form_class = AccountTypeSelectForm

    def get(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        account_type = self.request.GET.get("account_type", None)
        if not account_type:
            return super().get(request, *args, **kwargs)
        return redirect(
            reverse(
                "organization_member_add",
                kwargs={"organization_code": self.organization.code, "account_type": account_type},
            )
        )

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        breadcrumbs = super().build_breadcrumbs()
        breadcrumbs.append(
            {
                "url": reverse(
                    "organization_member_add_account_type", kwargs={"organization_code": self.organization.code}
                ),
                "text": _("Add member"),
            }
        )
        return breadcrumbs


class OrganizationMemberAddView(
    OrganizationPermissionRequiredMixin, OrganizationMemberBreadcrumbsMixin, OrganizationView, FormView
):
    """
    View to create a new member. Step 2: account setup.
    """

    template_name = "organizations/organization_member_add.html"
    form_class = MemberRegistrationForm
    permission_required = "tools.add_organizationmember"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        kwargs["account_type"] = self.kwargs["account_type"]
        return kwargs

    def form_valid(self, form):
        trusted_clearance_level = form.cleaned_data.get("trusted_clearance_level")
        if trusted_clearance_level and int(trusted_clearance_level) < DNS_REPORT_LEAST_CLEARANCE_LEVEL:
            clearance_level_warning_dns_report(self.request, trusted_clearance_level)
        self.add_success_notification()
        return super().form_valid(form)

    def add_success_notification(self):
        success_message = _("Member added successfully.")
        messages.add_message(self.request, messages.SUCCESS, success_message)

    def get_success_url(self, **kwargs):
        return reverse_lazy("organization_member_list", kwargs={"organization_code": self.organization.code})

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        breadcrumbs = super().build_breadcrumbs()
        breadcrumbs.extend(
            [
                {
                    "url": reverse(
                        "organization_member_add_account_type", kwargs={"organization_code": self.organization.code}
                    ),
                    "text": _("Add member"),
                }
            ]
        )
        return breadcrumbs


class DownloadMembersTemplateView(OrganizationPermissionRequiredMixin, OrganizationView):
    permission_required = "tools.add_organizationmember"

    def get(self, request, **kwargs):
        """Create a csv file with the right columns to download as a template for uploading organization members"""

        template = ",".join(MEMBER_UPLOAD_COLUMNS)

        return FileResponse(io.BytesIO(template.encode()), filename=f"{self.organization}_organization_members.csv")


class MembersUploadView(
    OrganizationPermissionRequiredMixin, OrganizationMemberBreadcrumbsMixin, OrganizationView, FormView
):
    """
    View to upload multiple new members with a CSV file.
    """

    template_name = "organizations/organization_member_upload.html"
    form_class = UploadCSVForm
    permission_required = "tools.add_organizationmember"

    def get_success_url(self):
        return reverse_lazy("organization_member_list", kwargs={"organization_code": self.organization.code})

    def form_valid(self, form):
        self.process_csv(form)
        return super().form_valid(form)

    def process_csv(self, form: Form) -> None:
        csv_raw_data = form.cleaned_data["csv_file"].read()
        csv_data = io.StringIO(csv_raw_data.decode("UTF-8"))

        try:
            for row in csv.DictReader(csv_data, delimiter=",", quotechar='"'):
                if not row:
                    continue  # skip empty lines

                try:
                    full_name, email, account_type, trusted_clearance, acknowledged_clearance = (
                        row["full_name"],
                        row["email"],
                        row["account_type"],
                        int(row["trusted_clearance_level"]),
                        int(row["acknowledged_clearance_level"]),
                    )
                except KeyError:
                    messages.add_message(self.request, messages.ERROR, _("The csv file is missing required columns"))
                    return

                try:
                    with transaction.atomic():
                        # We save all the relevant models and raise an exception on failure to revert the transaction
                        self.save_models(full_name, email, account_type, trusted_clearance, acknowledged_clearance)
                except ObjectDoesNotExist:
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        _("Invalid account type: '{account_type}'").format(account_type=account_type),
                    )
                    logger.exception("Invalid group")
                except ValidationError:
                    messages.add_message(
                        self.request, messages.WARNING, _("Invalid data for: '{email}'").format(email=email)
                    )
                    logger.warning("Invalid data", exc_info=True)
                except ValueError:
                    messages.add_message(
                        self.request, messages.WARNING, _("Invalid email address: '{email}'").format(email=email)
                    )
                    logger.warning("Invalid email address: %s", email)

            messages.add_message(self.request, messages.SUCCESS, _("Successfully processed users from csv."))
        except csv.Error:
            messages.add_message(
                self.request, messages.ERROR, _("Error parsing the csv file. Please verify its contents.")
            )
            logger.exception("Failed handling csv file")

    def save_models(
        self, name: str, email: str, account_type: str, trusted_clearance: int, acknowledged_clearance: int
    ) -> None:
        user, user_created = User.objects.get_or_create(email=email, defaults={"full_name": name})

        member_kwargs = {
            "organization": self.organization,
            "status": OrganizationMember.STATUSES.ACTIVE,
            "trusted_clearance_level": trusted_clearance,
            "acknowledged_clearance_level": acknowledged_clearance,
        }
        OrganizationMember(user=user, **member_kwargs).full_clean()  # Do validation before saving the model

        member, member_created = OrganizationMember.objects.get_or_create(
            user=user, organization=self.organization, defaults=member_kwargs
        )
        member.groups.add(Group.objects.get(name=account_type))

        if user_created:
            form = PasswordResetForm({"email": email})

            if not form.is_valid():
                logger.warning("Email not valid: %s", email)
                raise ValueError("Email not valid")

            form.save(
                email_template_name="registration_email.html",
                subject_template_name="registration_subject.txt",
                extra_email_context={"organization": self.organization.name},
                use_https=self.request.is_secure(),
                request=self.request,
            )

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        breadcrumbs = super().build_breadcrumbs()
        breadcrumbs.extend(
            [
                {
                    "url": reverse("organization_member_upload", kwargs={"organization_code": self.organization.code}),
                    "text": _("Add members"),
                }
            ]
        )
        return breadcrumbs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["criteria"] = CSV_CRITERIA

        return context
