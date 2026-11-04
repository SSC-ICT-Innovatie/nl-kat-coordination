from datetime import UTC, datetime
from uuid import uuid4

from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic.edit import FormView
from httpx import HTTPError
from tools.forms.paste_objects import PasteObjectsForm
from tools.ooi_blob import parse_ooi_blob

from octopoes.api.models import Declaration
from octopoes.models.ooi.network import Network

PASTE_OBJECTS_MIME_TYPE = "manual/txt"


class PasteObjects(OrganizationPermissionRequiredMixin, OrganizationView, FormView):
    """Add objects by pasting a blob of IPv4/IPv6 addresses, hostnames and URLs.

    The type of each value is detected automatically (see
    :mod:`tools.ooi_blob`), so users do not have to pick an object type
    upfront like the single-object or CSV upload flows require.
    """

    template_name = "paste_objects.html"
    form_class = PasteObjectsForm
    permission_required = "tools.can_scan_organization"

    def get_success_url(self):
        return reverse_lazy("ooi_list", kwargs={"organization_code": self.organization.code})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": _("Objects")},
            {
                "url": reverse("paste_objects", kwargs={"organization_code": self.organization.code}),
                "text": _("Paste objects"),
            },
        ]
        return context

    def form_valid(self, form):
        if not self.process_blob(form):
            return redirect("paste_objects", organization_code=self.organization.code)
        return super().form_valid(form)

    def add_error_notification(self, error_message):
        messages.add_message(self.request, messages.ERROR, error_message)
        return False

    def add_success_notification(self, success_message):
        messages.add_message(self.request, messages.SUCCESS, success_message)
        return True

    def process_blob(self, form) -> bool:
        network_name = form.cleaned_data["network"]
        parsed, errors = parse_ooi_blob(form.cleaned_data["objects"], network_name)

        if errors:
            line_numbers = ", ".join(map(str, sorted(errors)))
            self.add_error_notification(_("Object(s) could not be created for line number(s): ") + line_numbers)

        if not parsed:
            return False

        network = Network(name=network_name)
        raw_input = form.cleaned_data["objects"].encode("utf-8")
        task_id = uuid4()
        valid_time = datetime.now(UTC)

        declarations = [Declaration(ooi=network, valid_time=valid_time, task_id=task_id)]
        declarations.extend(Declaration(ooi=ooi, valid_time=valid_time, task_id=task_id) for _, ooi in parsed)

        self.raise_clearances(form, parsed)

        # The raw paste is stored as evidence so it stays auditable,
        # mirroring the CSV upload flow.
        self.bytes_client.add_manual_proof(task_id, raw_input, manual_mime_types={PASTE_OBJECTS_MIME_TYPE})

        try:
            self.octopoes_api_connector.save_many_declarations(declarations, sync=True)
        except HTTPError:
            return self.add_error_notification(_("Failed to save data from the pasted objects"))

        counts: dict[str, int] = {}
        for line_number, ooi in parsed:
            counts[ooi.object_type] = counts.get(ooi.object_type, 0) + 1
        summary = ", ".join(f"{count} × {object_type}" for object_type, count in sorted(counts.items()))

        return self.add_success_notification(_("Object(s) successfully added: ") + summary)

    def raise_clearances(self, form, parsed) -> None:
        """Request a clearance level for all parsed objects at once (best effort)."""
        level = form.cleaned_data["clearance_level"]
        if level == "":
            return
        try:
            self.raise_clearance_levels([ooi.reference for _, ooi in parsed], int(level))
        except Exception:  # noqa: BLE001 - a failing clearance request should not block object creation
            self.add_error_notification(_("Could not set the requested clearance level."))
