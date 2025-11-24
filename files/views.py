import django_filters
import structlog
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView
from django_filters.views import FilterView

from files.models import File
from openkat.mixins import OrganizationFilterMixin
from openkat.models import Organization
from openkat.permissions import KATModelPermissionRequiredMixin
from tasks.tasks import process_file

logger = structlog.get_logger(__name__)


class FileFilter(django_filters.FilterSet):
    file = django_filters.CharFilter(label="File name/Location", lookup_expr="icontains")
    organizations__name = django_filters.CharFilter(label="Organization", lookup_expr="icontains")
    task_result__task__data = django_filters.CharFilter(label="Source", lookup_expr="icontains")

    class Meta:
        model = File
        fields = ["file", "task_result__task__data", "organizations__name"]


class FileListView(OrganizationFilterMixin, FilterView):
    template_name = "file_list.html"
    model = File
    ordering = ["-id"]
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    filterset_class = FileFilter

    def get_queryset(self):
        super().get_queryset()  # Call to ensure any mixin logic is applied

        # Get base queryset without organization filtering
        queryset = File.objects.all()

        if not self.request.user.can_access_all_organizations:
            queryset = queryset.filter(organizations__members__user=self.request.user)

        if "task_id" in self.request.GET:
            queryset = queryset.filter(task_result__task__id=self.request.GET["task_id"])

        # Handle organization filtering for task__organization relationship
        organization_codes = self.request.GET.getlist("organization")
        if organization_codes:
            organizations = Organization.objects.filter(code__in=organization_codes)
            if organizations.exists():
                queryset = queryset.filter(task_result__task__organization__in=organizations)
            else:
                queryset = queryset.none()

        if "plugin_id" in self.request.GET:
            queryset = queryset.filter(task_result__task__data__plugin_id=self.request.GET["plugin_id"])

        return queryset.order_by(*self.ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("file_list"), "text": _("Files")}]

        return context


class FileCreateView(KATModelPermissionRequiredMixin, CreateView):
    model = File
    fields = ["file"]
    template_name = "file_form.html"

    object: File

    def form_invalid(self, form):
        logger.error("Failed creating file", errors=form.errors)
        return redirect(reverse("file_list"))

    def form_valid(self, form):
        result = super().form_valid(form)
        process_file(self.object)

        return result

    def get_success_url(self, **kwargs):
        redirect_url = self.get_form().data.get("current_url")

        if redirect_url and url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
            return redirect_url

        return reverse_lazy("file_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("file_list"), "text": _("Files")}]

        return context
