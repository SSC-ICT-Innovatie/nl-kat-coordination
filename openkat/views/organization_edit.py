from django.contrib import messages
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView

from openkat.forms import OrganizationUpdateForm
from openkat.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from openkat.models import Organization


class OrganizationEditView(OrganizationPermissionRequiredMixin, OrganizationView, UpdateView):
    form_class = OrganizationUpdateForm
    model = Organization
    template_name = "organizations/organization_edit.html"
    permission_required = "openkat.change_organization"

    object: Organization

    def get_object(self, queryset=None):
        return self.model.objects.get(id=self.kwargs["organization_id"])

    def get_success_url(self):
        messages.add_message(
            self.request, messages.SUCCESS, _("Organization %s successfully updated.") % (self.object.name)
        )
        return reverse("organization_settings", kwargs={"organization_id": self.object.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["breadcrumbs"] = [
            {"url": reverse("organization_list"), "text": "Organizations"},
            {
                "url": reverse("organization_settings", kwargs={"organization_id": self.object.id}),
                "text": self.object.name,
            },
            {"url": reverse("organization_edit", kwargs={"organization_id": self.object.id}), "text": _("Edit")},
        ]

        return context
