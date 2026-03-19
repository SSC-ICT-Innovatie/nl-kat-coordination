from enum import Enum

import structlog
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from httpx import RequestError
from tools.models import OrganizationMember
from tools.view_helpers import OrganizationMemberBreadcrumbsMixin

from rocky.forms import MemberFilterForm

logger = structlog.get_logger(__name__)


class PageActions(Enum):
    BLOCK = "block"
    UNBLOCK = "unblock"


class OrganizationMemberListView(
    OrganizationPermissionRequiredMixin, OrganizationMemberBreadcrumbsMixin, OrganizationView, ListView
):
    model = OrganizationMember
    context_object_name = "members"
    template_name = "organizations/organization_member_list.html"
    permission_required = "tools.view_organization"
    member_filter_form = MemberFilterForm

    def get_queryset(self):
        qs = super().get_queryset()
        form = self.member_filter_form(self.request.GET)
        if form.is_valid():
            current_status = form.cleaned_data.get("status")
            account_status = form.cleaned_data.get("blocked")
            return qs.filter(organization=self.organization, status__in=current_status, blocked__in=account_status)
        return qs

    def post(self, request, *args, **kwargs):
        if not self.organization_member.has_perm("tools.change_organizationmember"):
            raise PermissionDenied()
        if "action" not in self.request.POST:
            return self.get(request, *args, **kwargs)
        self.handle_page_action(request.POST.get("action"))
        return redirect(reverse("organization_member_list", kwargs={"organization_code": self.organization.code}))

    def handle_page_action(self, action: str) -> None:
        member_id = self.request.POST.get("member_id")
        organizationmember = self.model.objects.get(id=member_id)
        try:
            if action == PageActions.BLOCK.value:
                organizationmember.blocked = True
                messages.add_message(
                    self.request,
                    messages.SUCCESS,
                    _("Blocked member %s successfully.") % (organizationmember.user.email),
                )
            elif action == PageActions.UNBLOCK.value:
                organizationmember.blocked = False
                messages.add_message(
                    self.request,
                    messages.SUCCESS,
                    _("Unblocked member %s successfully.") % (organizationmember.user.email),
                )
            else:
                raise Exception(f"Unhandled allowed action: {action}")

            logger.info("Account status changed", event_code="900104", blocked=organizationmember.blocked)
            organizationmember.save()
        except RequestError as exception:
            messages.add_message(self.request, messages.ERROR, f"{action} failed: '{exception}'")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["member_filter_form"] = self.member_filter_form(self.request.GET)
        return context
