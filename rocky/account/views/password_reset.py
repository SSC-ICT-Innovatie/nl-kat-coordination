import structlog
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_totp.models import TOTPDevice

from account.forms import PasswordResetForm, SetPasswordForm

logger = structlog.get_logger(__name__)


class PasswordResetView(auth_views.PasswordResetView):
    """
    Handler to reset password with user's email address
    """

    template_name = "password_reset.html"
    email_template_name = "password_reset_email.html"
    subject_template_name = "password_reset_subject.txt"
    form_class = PasswordResetForm
    success_url = reverse_lazy("login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("login"), "text": _("Login")},
            {"url": reverse("password_reset"), "text": _("Reset password")},
        ]

        return context

    def form_valid(self, form):
        if self.is_smtp_valid():
            self.add_success_notification()
        else:
            self.add_error_notification()
        response = super().form_valid(form)
        logger.info("User reset password", event_code="900105", user=self.request.user)

        return response

    def is_smtp_valid(self):
        smtp_credentials = [settings.EMAIL_HOST, settings.EMAIL_PORT]
        return not ("" in smtp_credentials or None in smtp_credentials)

    def add_error_notification(self):
        if settings.HELP_DESK_EMAIL:
            error_message = _(
                "We couldn't send a password reset link. Contact " + settings.HELP_DESK_EMAIL + " for support."
            )
        else:
            error_message = _("We couldn't send a password reset link. Contact your system administrator.")
        messages.add_message(self.request, messages.ERROR, error_message)

    def add_success_notification(self):
        success_message = (
            "We've emailed you instructions for setting your password. You should receive the email shortly!"
        )
        messages.add_message(self.request, messages.SUCCESS, success_message)


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """
    Views a form so user can enter a new password and password confirmation.
    """

    template_name = "password_reset_confirm.html"
    form_class = SetPasswordForm
    success_url = reverse_lazy("login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("login"), "text": "Login"},
            {"url": "", "text": "Confirm reset password"},
        ]
        return context

    def remove_twofactor_device(self):
        """
        After password reset, the user must create a new 2auth token.
        """
        device = TOTPDevice.objects.filter(user=self.user.pk).exists()
        if device:
            device = TOTPDevice.objects.get(user=self.user.pk)
            device.delete()

    def form_valid(self, form):
        form_valid = super().form_valid(form)
        self.remove_twofactor_device()
        self.add_success_notification()
        return form_valid

    def add_success_notification(self):
        success_message = "Password reset is successfully done."
        messages.add_message(self.request, messages.SUCCESS, success_message)
