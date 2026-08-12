from account.forms import IndemnificationAddForm
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.urls import reverse_lazy
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from tools.models import Indemnification


class IndemnificationAddView(OrganizationPermissionRequiredMixin, OrganizationView, FormView):
    template_name = "indemnification_add.html"
    form_class = IndemnificationAddForm
    permission_required = "tools.add_indemnification"

    def post(self, request, *args, **kwargs):
        Indemnification.objects.get_or_create(user=self.request.user, organization=self.organization)
        self.add_success_notification()
        return super().post(request, *args, **kwargs)

    def get_success_url(self) -> str:
        return reverse_lazy("organization_settings", kwargs={"organization_code": self.organization.code})

    def add_success_notification(self):
        success_message = _("Indemnification successfully set.")
        messages.add_message(self.request, messages.SUCCESS, success_message)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["indemnification_present"] = Indemnification.objects.filter(
            user=self.request.user, organization=self.organization
        )
        context["breadcrumbs"] = [
            {
                "url": reverse("organization_settings", kwargs={"organization_code": self.organization.code}),
                "text": "Settings",
            },
            {
                "url": reverse("indemnification_add", kwargs={"organization_code": self.organization.code}),
                "text": _("Add indemnification"),
            },
        ]

        return context
