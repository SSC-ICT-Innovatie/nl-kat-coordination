from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView


class PrivacyStatementView(TemplateView):
    template_name = "legal/privacy_statement.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["breadcrumbs"] = [{"url": reverse("privacy_statement"), "text": _("Privacy Statement")}]

        return context
