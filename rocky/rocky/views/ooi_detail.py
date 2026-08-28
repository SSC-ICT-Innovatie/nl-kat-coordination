import json
from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from jsonschema.validators import Draft202012Validator
from katalogus.client import Boefje
from reports.report_types.helpers import get_report_types_for_ooi
from tools.forms.ooi import PossibleBoefjesFilterForm
from tools.forms.scheduler import OOIDetailTaskFilterForm
from tools.ooi_helpers import format_display

from octopoes.models import Reference
from octopoes.models.ooi.question import Question
from rocky.views.ooi_detail_related_object import OOIFindingManager, OOIRelatedObjectManager
from rocky.views.ooi_view import BaseOOIDetailView
from rocky.views.tasks import TaskListView


class OOIDetailView(BaseOOIDetailView, OOIRelatedObjectManager, OOIFindingManager, TaskListView):
    template_name = "oois/ooi_detail.html"
    task_filter_form = OOIDetailTaskFilterForm
    task_type = "boefje"

    def post(self, request, *args, **kwargs):
        if self.action == self.CHANGE_CLEARANCE_LEVEL:
            self.set_clearance_level()
        elif self.action == self.SUBMIT_ANSWER:
            self.answer_ooi_questions()
        elif self.action == self.START_SCAN:
            self.start_boefje_scan()
        return super().post(request, *args, **kwargs)

    def set_clearance_level(self) -> None:
        if not self.indemnification_present:
            self.indemnification_error()
            return
        try:
            clearance_level = int(self.request.POST["level"])
            self.can_raise_clearance_level(self.ooi, clearance_level)  # returns appropriate messages
        except (ValueError, KeyError):
            messages.error(
                self.request, _("Cannot set clearance level. It must be provided and must be a valid number.")
            )

    def answer_ooi_questions(self) -> None:
        if not isinstance(self.ooi, Question):
            messages.error(self.request, _("Only Question OOIs can be answered."))
            return

        schema_answer = self.request.POST.get("schema", "")
        parsed_schema_answer = json.loads(schema_answer)
        validator = Draft202012Validator(json.loads(self.ooi.json_schema))

        if not validator.is_valid(parsed_schema_answer):
            for error in validator.iter_errors(parsed_schema_answer):
                messages.error(self.request, error.message)
            return

        raw = json.dumps(
            {"schema": self.ooi.schema_id, "answer": parsed_schema_answer, "answer_ooi": self.ooi.ooi}
        ).encode()
        self.bytes_client.upload_raw(raw, {"answer"}, self.ooi.primary_key)
        messages.success(self.request, _("Question has been answered."))

    def start_boefje_scan(self) -> None:
        boefje_id = self.request.POST.get("boefje_id")
        boefje = self.get_katalogus().get_plugin(boefje_id)
        ooi_id = self.request.GET.get("ooi_id")
        ooi = self.get_single_ooi(pk=ooi_id)
        self.run_boefje(boefje, ooi)

    def get_task_filters(self) -> dict[str, str | datetime | None]:
        filters = super().get_task_filters()
        filters["filters"]["filters"].append(
            {"column": "data", "field": "input_ooi", "operator": "==", "value": str(self.ooi)}
        )
        return filters

    def get_boefjes_filter_form(self):
        return PossibleBoefjesFilterForm(self.request.GET)

    def get_boefjes_for_ooi(self, boefjes: list[Boefje]) -> list[Boefje]:
        return [
            boefje
            for boefje in boefjes
            if boefje.enabled
            and self.ooi.__class__ in boefje.consumes
            and self.ooi.scan_profile is not None
            and self.ooi.scan_profile.level >= boefje.scan_level.value
        ]

    def get_boefjes_exceeding_ooi_clearance_level(self, boefjes: list[Boefje]) -> list[Boefje]:
        """Get Boefjes that exceeds OOI clearance level"""

        return [
            boefje
            for boefje in boefjes
            if boefje
            and boefje.enabled
            and self.ooi.__class__ in boefje.consumes
            and self.ooi.scan_profile is not None
            and boefje.scan_level.value > self.ooi.scan_profile.level
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["ooi"] = self.ooi

        enabled_boefjes = self.get_katalogus().get_enabled_boefjes()
        ooi_boefjes = self.get_boefjes_for_ooi(enabled_boefjes)

        filter_form = self.get_boefjes_filter_form()

        # When a user wants to view boefjes that can't scan ooi, because the ooi does not have enough clearance level.
        if self.ooi.scan_profile and filter_form.is_valid() and filter_form.cleaned_data["show_all"]:
            exceeding_boefjes = self.get_boefjes_exceeding_ooi_clearance_level(enabled_boefjes)

            context["boefjes"] = ooi_boefjes + exceeding_boefjes
        else:
            context["boefjes"] = ooi_boefjes

        context.update(self.get_origins(self.ooi.reference, self.organization))
        if context["inferences"]:
            inference_params = self.octopoes_api_connector.list_origin_parameters(
                {inference.origin.id for inference in context["inferences"]}, self.observed_at
            )
            inference_params_per_inference = defaultdict(list)
            for inference_param in inference_params:
                inference_params_per_inference[inference_param.origin_id].append(inference_param)

            inference_origin_params: list[tuple] = []
            for inference in context["inferences"]:
                inference_origin_params.append((inference, inference_params_per_inference[inference.origin.id]))

            context["inference_origin_params"] = inference_origin_params
        else:
            context["inference_origin_params"] = None
        context["member"] = self.organization_member

        # TODO: generic solution to render ooi fields properly: https://github.com/minvws/nl-kat-coordination/issues/145
        context["object_details"] = format_display(self.get_ooi_properties(self.ooi), ignore=["json_schema"])
        context["ooi_types"] = self.get_ooi_types_input_values(self.ooi)

        context["is_question"] = isinstance(self.ooi, Question)
        context["ooi_past_due"] = context["observed_at"].date() < datetime.utcnow().date()
        context["related"] = self.get_related_objects(context["observed_at"])

        context["count_findings_per_severity"] = dict(self.count_findings_per_severity())
        context["severity_summary_totals"] = sum(context["count_findings_per_severity"].values())

        context["possible_boefjes_filter_form"] = self.get_boefjes_filter_form()
        context["organization_indemnification"] = self.indemnification_present

        context["possible_reports"] = [
            report.class_attributes() for report in get_report_types_for_ooi(self.ooi.primary_key)
        ]

        if self.request.GET.get("show_clearance_level_inheritance"):
            clearance_level_inheritance = self.get_scan_profile_inheritance(self.ooi)
            formatted_inheritance = [
                {
                    "object_type": Reference.from_str(section.reference).class_,
                    "primary_key": section.reference,
                    "human_readable": Reference.from_str(section.reference).human_readable,
                    "level": section.level,
                }
                for section in clearance_level_inheritance
            ]
            context["clearance_level_inheritance"] = formatted_inheritance
        return context
