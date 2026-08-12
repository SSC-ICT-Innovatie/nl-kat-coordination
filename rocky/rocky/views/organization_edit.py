from account.forms import OrganizationUpdateForm
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView
from tools.models import Organization


class OrganizationEditView(OrganizationPermissionRequiredMixin, OrganizationView, UpdateView):
    form_class = OrganizationUpdateForm
    model = Organization
    template_name = "organizations/organization_edit.html"
    permission_required = "tools.change_organization"

    def get_object(self):
        return self.model.objects.get(code=self.kwargs["organization_code"])

    def get_success_url(self):
        messages.add_message(
            self.request, messages.SUCCESS, _("Organization %s successfully updated.") % (self.object.name)
        )
        return reverse("organization_settings", kwargs={"organization_code": self.object.code})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["breadcrumbs"] = [
            {"url": reverse("organization_list"), "text": "Organizations"},
            {
                "url": reverse("organization_settings", kwargs={"organization_code": self.object.code}),
                "text": self.object.name,
            },
            {"url": reverse("organization_edit", kwargs={"organization_code": self.object.code}), "text": _("Edit")},
        ]

        return context
