from datetime import UTC, datetime
from uuid import uuid4

from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django import forms
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic.edit import FormView
from httpx import HTTPError
from tools.forms.paste_objects import CLEARANCE_LEVEL_CHOICES, PasteObjectsForm
from tools.ooi_blob import parse_ooi_blob

from octopoes.api.models import Declaration
from octopoes.connector import ConnectorException
from octopoes.models.ooi.network import Network

PASTE_OBJECTS_MIME_TYPE = "manual/txt"


class PasteObjects(OrganizationPermissionRequiredMixin, OrganizationView, FormView):
    """Add objects by pasting a blob of IPv4/IPv6 addresses, subnets, hostnames and URLs.

    Works in two steps, like the dedicated subnet form: step 1 takes the
    pasted blob, step 2 shows the detected object types for review. The
    type of each value is detected automatically (see
    :mod:`tools.ooi_blob`), so users do not have to pick an object type
    upfront like the single-object flow requires.
    """

    template_name = "paste_objects.html"
    form_class = PasteObjectsForm
    permission_required = "tools.can_scan_organization"

    def get_form(self, form_class=None) -> PasteObjectsForm:
        form = super().get_form(form_class)

        networks = self.octopoes_api_connector.list_objects({Network}, datetime.now(UTC)).items
        form.fields["network"].choices = sorted({("internet", "internet")} | {(n.name, n.name) for n in networks})

        # Like SubnetAddView: only members who may set clearance levels get levels,
        # and only up to their own maximum ("" = unchanged is always offered).
        max_level = self.organization_member.max_clearance_level if self.can_set_clearance_level else -1
        form.fields["clearance_level"].choices = CLEARANCE_LEVEL_CHOICES[: max_level + 2]

        return form

    @property
    def can_set_clearance_level(self) -> bool:
        return self.may_update_clearance_level and self.organization_member.has_perm("tools.can_set_clearance_level")

    def get_success_url(self):
        return reverse_lazy("ooi_list", kwargs={"organization_code": self.organization.code})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["step"] = kwargs.get("step", 1)
        context["parsed"] = kwargs.get("parsed")
        context["errors"] = kwargs.get("errors", {})
        context["breadcrumbs"] = [
            {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": _("Objects")},
            {
                "url": reverse("paste_objects", kwargs={"organization_code": self.organization.code}),
                "text": _("Paste objects"),
            },
        ]
        return context

    def form_valid(self, form):
        if self.request.POST.get("step") == "2":
            if not self.process_blob(form):
                return redirect("paste_objects", organization_code=self.organization.code)
            return super().form_valid(form)
        return self.render_review(form)

    def render_review(self, form):
        """Show the detected object types per line and the clearance level select."""
        parsed, errors = parse_ooi_blob(form.cleaned_data["objects"], form.cleaned_data["network"])

        if not parsed:
            line_numbers = ", ".join(map(str, sorted(errors)))
            form.add_error("objects", _("Object(s) could not be created for line number(s): ") + line_numbers)
            return self.render_to_response(self.get_context_data(form=form, step=1))

        for field_name in ("objects", "network"):
            form.fields[field_name].widget = forms.HiddenInput()

        return self.render_to_response(self.get_context_data(form=form, step=2, parsed=parsed, errors=errors))

    def add_error_notification(self, error_message):
        messages.add_message(self.request, messages.ERROR, error_message)
        return False

    def add_success_notification(self, success_message):
        messages.add_message(self.request, messages.SUCCESS, success_message)
        return True

    def process_blob(self, form) -> bool:
        network_name = form.cleaned_data["network"]
        parsed, errors = parse_ooi_blob(form.cleaned_data["objects"], network_name)

        if not parsed:
            line_numbers = ", ".join(map(str, sorted(errors)))
            self.add_error_notification(_("Object(s) could not be created for line number(s): ") + line_numbers)
            return False

        network = Network(name=network_name)
        raw_input = form.cleaned_data["objects"].encode("utf-8")
        task_id = uuid4()
        valid_time = datetime.now(UTC)

        declarations = [Declaration(ooi=network, valid_time=valid_time, task_id=task_id)]
        for entry in parsed:
            for dependency in entry.dependencies:
                declarations.append(Declaration(ooi=dependency, valid_time=valid_time, task_id=task_id))
            declarations.append(Declaration(ooi=entry.ooi, valid_time=valid_time, task_id=task_id))

        self.declare_clearances(form, parsed)

        # The raw paste is stored as evidence so it stays auditable,
        # mirroring the CSV upload flow.
        self.bytes_client.add_manual_proof(task_id, raw_input, manual_mime_types={PASTE_OBJECTS_MIME_TYPE})

        try:
            self.octopoes_api_connector.save_many_declarations(declarations, sync=True)
        except (HTTPError, ConnectorException):
            return self.add_error_notification(_("Failed to save data from the pasted objects"))

        counts: dict[str, int] = {}
        for entry in parsed:
            counts[entry.ooi.object_type] = counts.get(entry.ooi.object_type, 0) + 1
        summary = ", ".join(f"{count} × {object_type}" for object_type, count in sorted(counts.items()))

        return self.add_success_notification(_("Object(s) successfully added: ") + summary)

    def declare_clearances(self, form, parsed) -> None:
        """Declare a clearance level for all parsed objects at once (best effort).

        A declared profile can override or lower an existing level, hence
        "declare" rather than "raise" (cf. underdarknl's review note).
        """
        level = form.cleaned_data["clearance_level"]
        if level == "" or not self.can_set_clearance_level:
            return
        try:
            self.raise_clearance_levels([entry.ooi.reference for entry in parsed], int(level))
        except Exception:  # noqa: BLE001 - a failing clearance request should not block object creation
            self.add_error_notification(_("Could not set the requested clearance level."))
