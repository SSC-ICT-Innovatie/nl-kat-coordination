import structlog
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import CreateView

from openkat.forms import OrganizationForm
from openkat.models import Organization, OrganizationMember

logger = structlog.get_logger(__name__)


class OrganizationAddView(PermissionRequiredMixin, CreateView):
    """View to create a new organization"""

    model = Organization
    template_name = "organizations/organization_add.html"
    form_class = OrganizationForm
    success_url = reverse_lazy("organization_list")
    permission_required = "openkat.add_organization"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("organization_list"), "text": _("Organizations")},
            {"url": reverse("organization_add"), "text": _("Setup")},
        ]
        return context

    def form_valid(self, form):
        self.object = form.save()

        try:
            member, created = OrganizationMember.objects.get_or_create(user=self.request.user, organization=self.object)
            member.acknowledged_clearance_level = 0
            member.trusted_clearance_level = 4
            member.save()
        except Exception:
            message = "An issue occurred while creating the organization"
            logger.exception(message)
            messages.add_message(self.request, messages.ERROR, _(message))

            return redirect(self.success_url)

        self.add_success_notification()
        return redirect(self.get_success_url())

    def add_success_notification(self):
        success_message = _("Organization added successfully.")
        messages.add_message(self.request, messages.SUCCESS, success_message)

    def handle_no_permission(self):
        messages.add_message(self.request, messages.ERROR, _("You are not allowed to add organizations."))
        return redirect("organization_list")
