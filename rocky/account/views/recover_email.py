from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView


class RecoverEmailView(TemplateView):
    """
    Handler for email recovery.
    """

    template_name = "recover_email.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["help_desk_email"] = settings.HELP_DESK_EMAIL
        context["breadcrumbs"] = [
            {"url": reverse("login"), "text": _("Login")},
            {"url": reverse("recover_email"), "text": _("Recover email address")},
        ]
        return context
