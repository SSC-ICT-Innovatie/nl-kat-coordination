from datetime import datetime, timezone
from urllib.parse import unquote

from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic.edit import FormView
from httpx import HTTPError, HTTPStatusError
from tools.forms.upload_raw import UploadRawForm
from tools.view_helpers import Breadcrumb, BreadcrumbsMixin

from octopoes.models.types import OOI_TYPES


class UploadRaw(OrganizationPermissionRequiredMixin, BreadcrumbsMixin, OrganizationView, FormView):
    template_name = "upload_raw.html"
    form_class = UploadRawForm
    permission_required = "tools.can_scan_organization"

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()
        if "mime_type" in self.kwargs:
            initial["mime_types"] = unquote(self.kwargs["mime_type"])
        elif "mime_types" in self.kwargs:
            initial["mime_types"] = unquote(self.kwargs["mime_types"])
        return initial

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        kwargs = {"organization_code": self.organization.code, "temporal_context": self.kwargs.get("temporal_context")}
        return [
            {"url": reverse("ooi_list", kwargs=kwargs), "text": _("Objects")},
            {"url": reverse("upload_raw", kwargs=kwargs), "text": _("Upload raw")},
        ]

    def get_success_url(self):
        return self.build_breadcrumbs()[0]["url"]

    def form_valid(self, form):
        if not self.process_raw(form):
            return redirect(self.build_breadcrumbs()[1]["url"])
        return super().form_valid(form)

    def add_error_notification(self, error_message):
        messages.add_message(self.request, messages.ERROR, error_message)
        return False

    def add_success_notification(self, success_message):
        messages.add_message(self.request, messages.SUCCESS, success_message)
        return True

    def process_raw(self, form):
        raw_file = form.cleaned_data["raw_file"]
        mime_types = form.cleaned_data["mime_types"]
        input_ooi = form.cleaned_data["ooi"]
        valid_time = None
        if "date" in form.cleaned_data:
            valid_time = form.cleaned_data["date"].replace(tzinfo=timezone.utc)

        try:
            self.bytes_client.upload_raw(
                raw_file.read(),
                mime_types,
                input_ooi=input_ooi.primary_key,
                input_dict=input_ooi.serialize(),
                valid_time=valid_time,
            )
        except HTTPStatusError as exc:
            return self.add_error_notification(
                _("Raw file could not be uploaded to Bytes: status code %d") % exc.response.status_code
            )
        except HTTPError as exc:
            return self.add_error_notification(_("Raw file could not be uploaded to Bytes: %s") % str(exc))
        else:
            self.add_success_notification(_("Raw file successfully added."))

    def get_form_kwargs(self):
        kwargs = {"connector": self.octopoes_api_connector, "ooi_list": self.get_ooi_options()}
        kwargs.update(super().get_form_kwargs())

        if "ooi_class" in kwargs:
            del kwargs["ooi_class"]

        observed_at = self.request.GET.get("observed_at")
        if observed_at:
            kwargs["observed_at"] = observed_at

        return kwargs

    def get_ooi_options(self) -> list[tuple[str, str]]:
        objects = self.octopoes_api_connector.list_objects(
            set(OOI_TYPES.values()), valid_time=datetime.now(timezone.utc)
        ).items

        options = [(o.primary_key, o.get_ooi_type()) for o in objects]

        return options
