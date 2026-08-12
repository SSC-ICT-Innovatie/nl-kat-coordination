import structlog
from account.forms import OrganizationMemberEditForm
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView
from tools.models import GROUP_CLIENT, OrganizationMember

logger = structlog.get_logger(__name__)


class OrganizationMemberEditView(
    OrganizationPermissionRequiredMixin, UserPassesTestMixin, OrganizationView, UpdateView
):
    form_class = OrganizationMemberEditForm
    model = OrganizationMember
    template_name = "organizations/organization_member_edit.html"
    object: OrganizationMember
    permission_required = "tools.change_organizationmember"

    def test_func(self):
        return (
            not self.get_object().user.is_superuser or self.request.user.is_superuser
        ) and self.get_object().organization == self.organization

    def get_form(self):
        form = super().get_form()
        group = self.object.user.groups.all().values_list("name", flat=True)

        # Make sure the logged in user can't block himself out of the organisation.
        if self.object.user == self.request.user:
            form.fields["blocked"].disabled = True

        # Since clients aren't allowed to scan and set clearance levels, disable the truste clearance level field.
        if GROUP_CLIENT in group:
            form.fields["trusted_clearance_level"].disabled = True
        return form

    def get_success_url(self):
        messages.add_message(
            self.request, messages.SUCCESS, _("Member %s successfully updated.") % (self.object.user.full_name)
        )
        return reverse("organization_member_list", kwargs={"organization_code": self.organization.code})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["breadcrumbs"] = [
            {
                "url": reverse("organization_member_list", kwargs={"organization_code": self.organization.code}),
                "text": _("Members"),
            },
            {
                "url": reverse(
                    "organization_member_edit",
                    kwargs={"organization_code": self.organization.code, "pk": self.object.id},
                ),
                "text": _("Edit member"),
            },
        ]

        return context

    def form_valid(self, form):
        tcl = form.cleaned_data["trusted_clearance_level"]
        acl = form.cleaned_data["acknowledged_clearance_level"]
        if not tcl:
            tcl = -1
        else:
            logger.info("Setting trusted clearance level", event_code="900108", level=tcl, user=form.instance.id)

        if not acl:
            acl = -1

        if int(tcl) < int(acl):
            messages.add_message(
                self.request,
                messages.INFO,
                _(
                    "The updated trusted clearance level of L%s is lower then the member's "
                    "acknowledged clearance level of L%s. This member only has clearance for level L%s. "
                    "For this reason the acknowledged clearance level has been set at the same level "
                    "as trusted clearance level."
                )
                % (tcl, acl, tcl),
            )
        if int(tcl) > int(acl):
            messages.add_message(
                self.request,
                messages.INFO,
                _(
                    "You have trusted this member with a higher trusted level than member acknowledged. "
                    "Member must first accept this level to use it."
                ),
            )
        return super().form_valid(form)
