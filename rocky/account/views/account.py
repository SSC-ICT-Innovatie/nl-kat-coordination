from enum import Enum

import structlog
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from tools.models import OrganizationMember

from account.mixins import OrganizationView

logger = structlog.get_logger(__name__)


class PageActions(Enum):
    ACCEPT_CLEARANCE = "accept_clearance"
    WITHDRAW_ACCEPTANCE = "withdraw_acceptance"


class OOIClearanceMixin:
    request: HttpRequest
    organization_member: OrganizationMember

    def post(self, request, *args, **kwargs):
        if "action" in self.request.POST:
            self.handle_page_action(request.POST["action"])
        # Mypy doesn't have the information to understand this
        return self.get(request, *args, **kwargs)  # type: ignore[attr-defined]

    def handle_page_action(self, action: str) -> None:
        if action == PageActions.ACCEPT_CLEARANCE.value:
            self.organization_member.acknowledged_clearance_level = self.organization_member.trusted_clearance_level
        elif action == PageActions.WITHDRAW_ACCEPTANCE.value:
            self.organization_member.acknowledged_clearance_level = -1

        self.organization_member.save()
        logger.info(
            "Set accepted clearance level",
            event_code="900109",
            member=self.organization_member.id,
            level=self.organization_member.acknowledged_clearance_level,
        )


class AccountView(OrganizationView, TemplateView, OOIClearanceMixin):
    template_name = "account_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": "", "text": _("Account details")}]
        return context
