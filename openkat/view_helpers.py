from typing import TypedDict

from django.http import HttpRequest
from django.urls.base import reverse, reverse_lazy
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from openkat.models import Organization


class Breadcrumb(TypedDict):
    text: str | Promise
    url: str


class BreadcrumbsMixin:
    breadcrumbs: list[Breadcrumb] = []

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        return self.breadcrumbs.copy()

    def get_context_data(self, **kwargs):
        # Mypy doesn't understand the way mixins are used
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        context["breadcrumbs"] = self.build_breadcrumbs()
        return context


class Step(TypedDict):
    text: str
    url: str


class StepsMixin:
    request: HttpRequest
    steps: list[Step] = []
    current_step: int | None = None

    def get_current_step(self):
        if self.current_step is None:
            return int(self.request.GET.get("current_step"))
        return self.current_step

    def set_current_stepper_url(self, url):
        self.steps[self.get_current_step() - 1]["url"] = url

    def build_steps(self) -> list[Step]:
        return self.steps.copy()

    def get_context_data(self, **kwargs):
        # Mypy doesn't understand the way mixins are used
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        context["steps"] = self.build_steps()
        context["current_step"] = self.get_current_step()

        return context


class OrganizationBreadcrumbsMixin(BreadcrumbsMixin):
    breadcrumbs = [{"url": reverse_lazy("organization_list"), "text": _("Organizations")}]


class OrganizationDetailBreadcrumbsMixin(BreadcrumbsMixin):
    organization: Organization

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        return [
            {
                "url": reverse("organization_settings", kwargs={"organization_code": self.organization.code}),
                "text": _("Settings"),
            }
        ]


class OrganizationMemberBreadcrumbsMixin(BreadcrumbsMixin):
    organization: Organization

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        return [
            {
                "url": reverse("organization_member_list", kwargs={"organization_code": self.organization.code}),
                "text": _("Members"),
            }
        ]
