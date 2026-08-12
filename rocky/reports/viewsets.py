from datetime import datetime, timezone
from uuid import uuid4

from account.mixins import OrganizationAPIMixin
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from structlog import get_logger
from tools.ooi_helpers import create_ooi
from tools.view_helpers import url_with_querystring

from octopoes.models import Reference
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.reports import ReportRecipe
from reports.serializers import ReportRecipeSerializer, ReportSerializer
from rocky.scheduler import ReportTask, ScheduleRequest
from rocky.views.mixins import ReportList

logger = get_logger(__name__)


class ReportViewSet(OrganizationAPIMixin, viewsets.ReadOnlyModelViewSet):
    # There are no extra permissions needed to view reports, so IsAuthenticated
    # is enough for list/retrieve. OrganizationAPIMixin will check if the user
    # is a member of the requested organization.
    permission_classes = [IsAuthenticated]
    serializer_class = ReportSerializer

    def get_queryset(self):
        return ReportList(self.octopoes_api_connector, self.valid_time)

    def get_object(self):
        pk = self.kwargs["pk"]

        try:
            return self.octopoes_api_connector.get(Reference.from_str(f"Report|{pk}"), valid_time=self.valid_time)
        except ObjectNotFoundException as e:
            raise Http404 from e

    @action(detail=True)
    def pdf(self, request, pk):
        report_ooi_id = f"Report|{pk}"

        url = url_with_querystring(
            reverse("view_report_pdf", kwargs={"organization_code": self.organization.code}),
            True,
            report_id=report_ooi_id,
            observed_at=self.valid_time.isoformat(),
        )

        return HttpResponseRedirect(redirect_to=url)


class ReportRecipeViewSet(OrganizationAPIMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ReportRecipeSerializer

    def list(self, request, *args, **kwargs) -> Response:
        self.paginator.limit = self.paginator.get_limit(request)
        self.paginator.offset = self.paginator.get_offset(request)

        paginated_response = self.octopoes_api_connector.list_objects(
            types={ReportRecipe}, limit=self.paginator.limit, offset=self.paginator.offset, valid_time=self.valid_time
        )

        self.paginator.count = paginated_response.count

        serializer = ReportRecipeSerializer(paginated_response.items, many=True)

        return self.get_paginated_response(serializer.data)

    # The HTML renderer wants this to be defined, but doesn't seem to use what
    # is returned.
    def get_queryset(self):
        return []

    def get_object(self) -> ReportRecipe:
        pk = self.kwargs["pk"]

        try:
            recipe = self.octopoes_api_connector.get(
                Reference.from_str(f"ReportRecipe|{pk}"), valid_time=self.valid_time
            )
        except ObjectNotFoundException as e:
            raise Http404 from e

        return recipe

    def get_schedule_id(self, pk: str) -> str | None:
        filters = {"filters": [{"column": "data", "field": "report_recipe_id", "operator": "eq", "value": pk}]}

        response = self.scheduler_client.post_schedule_search(filters)

        if not response.results:
            return None

        return str(response.results[0].id)

    def perform_create(self, serializer: ReportRecipeSerializer) -> None:
        data = serializer.validated_data

        deadline_at = data.pop("start_date", None)

        update = False
        if "recipe_id" in data:
            # Update the already existing recipe if a recipe with this id already exists.
            try:
                self.octopoes_api_connector.get(
                    Reference.from_str(f"ReportRecipe|{data['recipe_id']}"), valid_time=self.valid_time
                )
            except ObjectNotFoundException:
                pass
            else:
                update = True
        else:
            data["recipe_id"] = uuid4()

        report_recipe = ReportRecipe.model_validate(data)

        create_ooi(
            api_connector=self.octopoes_api_connector,
            bytes_client=self.bytes_client,
            ooi=report_recipe,
            observed_at=self.valid_time,
        )

        if update:
            schedule_id = self.get_schedule_id(str(data["recipe_id"]))
            if not schedule_id:
                raise APIException("Schedule for recipe does not exist")

            if deadline_at:
                self.scheduler_client.patch_schedule(
                    schedule_id, params={"schedule": report_recipe.cron_expression, "deadline_at": deadline_at}
                )
            else:
                self.scheduler_client.patch_schedule(schedule_id, params={"schedule": report_recipe.cron_expression})
        else:
            report_task = ReportTask(
                organisation_id=self.organization.code, report_recipe_id=str(report_recipe.recipe_id)
            ).model_dump()

            if not deadline_at:
                deadline_at = datetime.now(timezone.utc).date().isoformat()

            schedule_request = ScheduleRequest(
                scheduler_id="report",
                organisation=self.organization.code,
                data=report_task,
                schedule=report_recipe.cron_expression,
                deadline_at=deadline_at,
            )

            self.scheduler_client.post_schedule(schedule=schedule_request)

        # This will make DRF return the new instance with the generated id
        serializer.instance = report_recipe

    def perform_update(self, serializer: ReportRecipeSerializer) -> None:
        schedule_id = self.get_schedule_id(self.kwargs["pk"])
        if not schedule_id:
            raise APIException("Schedule for recipe does not exist")

        deadline_at = serializer.validated_data.pop("start_date", datetime.now(timezone.utc).date().isoformat())
        report_recipe = ReportRecipe.model_validate({"recipe_id": self.kwargs["pk"], **serializer.validated_data})

        create_ooi(
            api_connector=self.octopoes_api_connector,
            bytes_client=self.bytes_client,
            ooi=report_recipe,
            observed_at=self.valid_time,
        )

        self.scheduler_client.patch_schedule(
            schedule_id, params={"schedule": report_recipe.cron_expression, "deadline_at": deadline_at}
        )

        # This will make DRF return the new instance
        serializer.instance = report_recipe

    def perform_destroy(self, instance: ReportRecipe) -> None:
        schedule_id = self.get_schedule_id(self.kwargs["pk"])

        # If we would return an error here this would mean we can never delete a
        # recipe in octopoes that doesn't have a schedule anymore. This could
        # happen if something goes wrong with deleting the recipe in octopoes
        # after we deleted the schedule.
        if schedule_id:
            self.scheduler_client.delete_schedule(schedule_id)
        else:
            self.logger.error("Schedule not found when deleting report recipe", report_recipe_id=self.kwargs["pk"])

        self.octopoes_api_connector.delete(
            Reference.from_str(f"ReportRecipe|{instance.recipe_id}"), valid_time=self.valid_time
        )
