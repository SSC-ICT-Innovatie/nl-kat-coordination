import json

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from rocky.scheduler import SchedulerError
from rocky.views.tasks import SchedulerView


class DownloadTaskDetail(SchedulerView):
    def get(self, request, *args, **kwargs):
        task_id = kwargs["task_id"]
        filename = "task_" + task_id + ".json"
        task_details = self.get_task_details(task_id)
        if task_details is not None:
            response = HttpResponse(json.dumps(task_details.model_dump(mode="json")), content_type="application/json")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return redirect(reverse("task_list", kwargs={"organization_code": self.organization.code}))


class TaskDetailView(SchedulerView, TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["task_id"] = kwargs["task_id"]
        try:
            context["task"] = self.get_task_details(context["task_id"])
        except SchedulerError as error:
            messages.error(self.request, error.message)
        return context


class BoefjeTaskDetailView(TaskDetailView):
    template_name = "tasks/boefje_task_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["breadcrumbs"] = [
            {"url": reverse("task_list", kwargs={"organization_code": self.organization.code}), "text": _("Tasks")},
            {
                "url": reverse(
                    "boefje_task_view",
                    kwargs={"organization_code": self.organization.code, "task_id": context["task_id"]},
                ),
                "text": context["task"].data.boefje.id,
            },
        ]

        return context


class NormalizerTaskJSONView(TaskDetailView):
    task_type = "normalizer"
    plugin_type = "normalizer"
    template_name = "tasks/normalizer_task_detail.html"

    def get(self, request, *args, **kwargs) -> JsonResponse | HttpResponse:
        task = self.get_json_task_details()
        if task is not None:
            return task
        return super().get(request, *args, **kwargs)
