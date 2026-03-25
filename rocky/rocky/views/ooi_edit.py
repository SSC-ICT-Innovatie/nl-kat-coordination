from datetime import datetime, timezone
from enum import Enum

from django.utils.translation import gettext_lazy as _
from tools.view_helpers import get_ooi_url

from rocky.views.ooi_view import BaseOOIFormView
from rocky.views.scheduler import SchedulerView


class OOIEditView(BaseOOIFormView, SchedulerView):
    template_name = "oois/ooi_edit.html"
    task_type = "report"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.ooi = self.get_ooi()
        self.ooi_class = self.get_ooi_class()

    def get_initial(self):
        initial = super().get_initial()

        for attr, value in self.ooi:
            if isinstance(value, list):
                initial[attr] = [str(x) for x in value]
            elif isinstance(value, Enum):
                initial[attr] = value.value
            elif isinstance(value, dict):
                # Config OOIs use dicts for their values
                initial[attr] = value
            else:
                initial[attr] = str(value) if value is not None else None

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user_id"] = self.request.user.id

        return kwargs

    def form_valid(self, form):
        form_data = form.cleaned_data
        report_recipe_id = form_data.get("recipe_id")
        cron_expression = form_data.get("cron_expression")

        # If the cron_expression of the ReportRecipe is changed, the scheduler must also be updated
        if report_recipe_id and cron_expression:
            deadline_at = datetime.now(timezone.utc).isoformat()
            filters = {
                "filters": [
                    {"column": "data", "field": "report_recipe_id", "operator": "eq", "value": report_recipe_id}
                ]
            }
            schedule = self.get_schedule_with_filters(filters)
            if schedule:
                self.edit_report_schedule(str(schedule.id), {"schedule": cron_expression, "deadline_at": deadline_at})

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Construct breadcrumbs
        breadcrumb_list = self.get_breadcrumb_list()
        breadcrumb_list.append(
            {"url": get_ooi_url("ooi_edit", self.ooi.primary_key, self.organization.code), "text": _("Edit")}
        )

        context["type"] = self.ooi_class.get_ooi_type()
        context["ooi_human_readable"] = self.ooi.human_readable
        context["breadcrumbs"] = breadcrumb_list

        return context
