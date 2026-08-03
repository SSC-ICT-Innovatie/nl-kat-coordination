from datetime import datetime, timezone
from functools import cached_property

import structlog
from account.mixins import OrganizationView
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from tools.models import OrganizationMember

logger = structlog.get_logger(__name__)
User = get_user_model()

SUPERUSER_ACCESS_GRANTED_EVENT_CODE = "900113"
SUPERUSER_ACCESS_REVOKED_EVENT_CODE = "900114"


class SuperuserAccessView(UserPassesTestMixin, OrganizationView, TemplateView):
    """Shared confirmation page base for granting/revoking installation-wide access.

    The actor must already be a superuser; the target is resolved only after the
    permission check so a non-superuser cannot probe membership IDs.
    """

    raise_exception = True
    action_label = ""

    @cached_property
    def member(self):
        """Resolve the target only after the actor has passed the permission check."""
        return get_object_or_404(
            OrganizationMember.objects.select_related("user"), pk=self.kwargs["pk"], organization=self.organization
        )

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["member"] = self.member
        context["breadcrumbs"] = [
            {
                "url": reverse("organization_member_list", kwargs={"organization_code": self.organization.code}),
                "text": _("Members"),
            },
            {
                "url": reverse(
                    "organization_member_edit",
                    kwargs={"organization_code": self.organization.code, "pk": self.member.id},
                ),
                "text": _("Edit member"),
            },
            {
                "url": self.request.path,
                "text": self.action_label,
            },
        ]
        return context

    def get_success_url(self):
        return reverse("organization_member_list", kwargs={"organization_code": self.organization.code})


class GrantSuperuserAccessView(SuperuserAccessView):
    """Grant installation-wide superuser access from an organization member page."""

    template_name = "organizations/organization_member_grant_superuser.html"
    action_label = _("Grant superuser access")

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            target_member = get_object_or_404(
                OrganizationMember.objects.select_for_update(), pk=kwargs["pk"], organization=self.organization
            )
            target_user = User.objects.select_for_update().get(pk=target_member.user_id)
            previous_is_superuser = target_user.is_superuser
            previous_is_staff = target_user.is_staff

            if not target_user.is_active:
                messages.warning(
                    request,
                    _("%(email)s is inactive and cannot be granted superuser access.") % {"email": target_user.email},
                )
                return HttpResponseRedirect(self.get_success_url())

            if previous_is_superuser and previous_is_staff:
                messages.warning(request, _("%(email)s already has superuser access.") % {"email": target_user.email})
                return HttpResponseRedirect(self.get_success_url())

            target_user.is_superuser = True
            target_user.is_staff = True
            target_user.save(update_fields=["is_superuser", "is_staff"])

            audit_event = {
                "event_code": SUPERUSER_ACCESS_GRANTED_EVENT_CODE,
                "actor_id": request.user.id,
                "actor_email": request.user.email,
                "target_id": target_user.id,
                "target_email": target_user.email,
                "previous_is_superuser": previous_is_superuser,
                "previous_is_staff": previous_is_staff,
                "is_superuser": target_user.is_superuser,
                "is_staff": target_user.is_staff,
                "changed_at": datetime.now(timezone.utc).isoformat(),
            }
            transaction.on_commit(lambda: logger.info("Superuser access granted", **audit_event))

        messages.success(request, _("Superuser access granted to %(email)s.") % {"email": target_user.email})
        return HttpResponseRedirect(self.get_success_url())


class RevokeSuperuserAccessView(SuperuserAccessView):
    """Revoke installation-wide superuser access from an organization member page."""

    template_name = "organizations/organization_member_revoke_superuser.html"
    action_label = _("Revoke superuser access")

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            target_member = get_object_or_404(
                OrganizationMember.objects.select_for_update(), pk=kwargs["pk"], organization=self.organization
            )
            target_user = User.objects.select_for_update().get(pk=target_member.user_id)
            previous_is_superuser = target_user.is_superuser
            previous_is_staff = target_user.is_staff

            if not previous_is_superuser:
                messages.warning(request, _("%(email)s does not have superuser access.") % {"email": target_user.email})
                return HttpResponseRedirect(self.get_success_url())

            # ponytail: last-superuser guard has a TOCTOU ceiling: two superusers
            # revoking two *different* superusers concurrently can each see a
            # remaining count of 1 and both proceed, leaving zero. A DB-level
            # constraint or advisory lock forbidding zero active superusers is
            # the upgrade path; until then recovery is `manage.py createsuperuser`.
            remaining_active_superusers = (
                User.objects.filter(is_superuser=True, is_active=True).exclude(pk=target_user.pk).count()
            )
            if remaining_active_superusers == 0:
                messages.warning(
                    request,
                    _(
                        "Revoking superuser access from %(email)s would leave this installation without any "
                        "active superuser. Promote another account first, or revoke it via Django administration."
                    )
                    % {"email": target_user.email},
                )
                return HttpResponseRedirect(self.get_success_url())

            target_user.is_superuser = False
            target_user.is_staff = False
            target_user.save(update_fields=["is_superuser", "is_staff"])

            audit_event = {
                "event_code": SUPERUSER_ACCESS_REVOKED_EVENT_CODE,
                "actor_id": request.user.id,
                "actor_email": request.user.email,
                "target_id": target_user.id,
                "target_email": target_user.email,
                "previous_is_superuser": previous_is_superuser,
                "previous_is_staff": previous_is_staff,
                "is_superuser": target_user.is_superuser,
                "is_staff": target_user.is_staff,
                "changed_at": datetime.now(timezone.utc).isoformat(),
            }
            transaction.on_commit(lambda: logger.info("Superuser access revoked", **audit_event))

        messages.success(request, _("Superuser access revoked from %(email)s.") % {"email": target_user.email})
        return HttpResponseRedirect(self.get_success_url())
