from typing import Any

import django_filters
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_filters.views import FilterView

from openkat.mixins import OrganizationFilterMixin
from openkat.models import Organization
from openkat.permissions import KATModelPermissionRequiredMixin
from plugins.models import BusinessRule, Plugin, ScanLevel
from tasks.models import Schedule, Task
from tasks.views import TaskFilter


class PluginFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(label="Name", lookup_expr="icontains", widget=forms.TextInput())
    oci_image = django_filters.CharFilter(label="Container image", lookup_expr="icontains", widget=forms.TextInput())
    scan_level = django_filters.ChoiceFilter(label="Scan level", choices=ScanLevel.choices)

    class Meta:
        model = Plugin
        fields = ["name", "oci_image", "scan_level"]


class PluginVariantFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(label="Name", lookup_expr="icontains", widget=forms.TextInput())
    scan_level = django_filters.ChoiceFilter(label="Scan level", choices=ScanLevel.choices)

    class Meta:
        model = Plugin
        fields = ["name", "scan_level"]


class PluginListView(OrganizationFilterMixin, FilterView):
    template_name = "plugin_list.html"
    fields = ["enabled_plugins"]
    model = Plugin
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    filterset_class = PluginFilter

    def get_queryset(self) -> QuerySet:
        super().get_queryset()  # Call to ensure any mixin logic is applied

        plugins = Plugin.objects.all()
        order_by = self.request.GET.get("order_by", "name")
        sorting_order = self.request.GET.get("sorting_order", "asc")

        if order_by and sorting_order == "desc":
            return plugins.order_by(f"-{order_by}")

        return plugins.order_by(order_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("plugin_list"), "text": _("Plugins")}]
        context["order_by"] = self.request.GET.get("order_by")
        context["sorting_order"] = self.request.GET.get("sorting_order", "asc")
        context["sorting_order_class"] = "ascending" if context["sorting_order"] == "asc" else "descending"

        organization_ids = self.request.GET.getlist("organization")

        if organization_ids:
            organizations = Organization.objects.filter(id__in=organization_ids)
            schedule_plugin_ids = (
                Schedule.objects.filter(organization__in=organizations).values_list("plugin_id", flat=True).distinct()
            )
            plugins_with_schedules = set(schedule_plugin_ids)
        else:
            schedule_plugin_ids = (
                Schedule.objects.filter(organization=None).values_list("plugin_id", flat=True).distinct()
            )
            plugins_with_schedules = set(schedule_plugin_ids)

        context["plugins_with_schedules"] = plugins_with_schedules

        return context


class PluginDetailView(OrganizationFilterMixin, DetailView):
    template_name = "plugin.html"
    model = Plugin
    object: Plugin

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("plugin_list"), "text": _("Plugins")},
            {"url": reverse("plugin_detail", kwargs={"pk": self.object.pk}), "text": _("Plugin details")},
        ]

        organization_ids = self.request.GET.getlist("organization")
        if organization_ids:
            organizations = Organization.objects.filter(id__in=organization_ids)
            context["has_schedules"] = Schedule.objects.filter(
                plugin=self.object, organization__in=organizations
            ).exists()
        else:
            # Check for global schedules
            context["has_schedules"] = Schedule.objects.filter(plugin=self.object, organization=None).exists()

        return context


class PluginIdDetailView(PluginDetailView):
    slug_url_kwarg = "plugin_id"
    slug_field = "plugin_id"


class PluginScansDetailView(PluginDetailView):
    template_name = "plugin_scans.html"
    filterset_class = TaskFilter
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE

    def get_tasks(self):
        return Task.objects.filter(data__plugin_id=self.object.plugin_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filterset = self.filterset_class(self.request.GET, queryset=self.get_tasks())
        context["filter"] = filterset
        context["task_list"] = filterset.qs.order_by("-ended_at")
        return context


class PluginVariantsDetailView(PluginDetailView):
    template_name = "plugin_variants.html"
    filterset_class = PluginVariantFilter
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE

    def get_variants(self):
        return Plugin.objects.filter(oci_image=self.object.oci_image)

    def filter_variants(self, filterset):
        return filterset.qs.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filterset = self.filterset_class(self.request.GET, queryset=self.get_variants())
        context["filter"] = filterset
        context["variants"] = self.filter_variants(filterset)
        return context


class PluginCreateView(KATModelPermissionRequiredMixin, CreateView):
    model = Plugin
    fields = ["plugin_id", "name", "consumes", "description", "scan_level", "batch_size", "oci_image", "oci_arguments"]
    template_name = "plugin_form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["description"].widget.attrs["rows"] = 3
        return form

    def get_form_kwargs(self):
        if self.request.method == "POST" and "plugin_id" in self.request.GET:
            if "duplicate" in self.request.GET and self.request.GET["duplicate"]:
                return super().get_form_kwargs()

            self.object = Plugin.objects.get(pk=self.request.GET["plugin_id"])
            return super().get_form_kwargs()

        if "plugin_id" in self.request.GET:
            self.object = Plugin.objects.get(pk=self.request.GET["plugin_id"])

        kwargs = super().get_form_kwargs()

        if "duplicate" in self.request.GET and self.request.GET["duplicate"]:
            kwargs["initial"]["plugin_id"] = None
            kwargs["initial"]["name"] = None

        if "oci_arguments" in self.request.GET:
            oci_arg = self.request.GET["oci_arguments"]
            if "initial" not in kwargs:
                kwargs["initial"] = {}
            kwargs["initial"]["oci_arguments"] = [oci_arg]

        return kwargs

    def form_invalid(self, form):
        return redirect(reverse("plugin_list"))

    def get_success_url(self, **kwargs):
        redirect_url = self.get_form().data.get("current_url")

        if redirect_url and url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
            return redirect_url

        return reverse_lazy("plugin_list")


class PluginUpdateView(KATModelPermissionRequiredMixin, UpdateView):
    model = Plugin
    fields = ["plugin_id", "name", "consumes", "description", "scan_level", "batch_size", "oci_image", "oci_arguments"]
    template_name = "plugin_settings.html"
    object: Plugin

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["description"].widget.attrs["rows"] = 3
        return form

    def form_invalid(self, form):
        return reverse("plugin_detail", kwargs={"pk": self.object.pk})

    def get_success_url(self, **kwargs):
        return reverse("plugin_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plugin"] = self.object
        context["breadcrumbs"] = [
            {"url": reverse("plugin_list"), "text": _("Plugins")},
            {"url": reverse("plugin_detail", kwargs={"pk": self.object.pk}), "text": _("Plugin details")},
        ]

        return context


class PluginDeleteView(KATModelPermissionRequiredMixin, DeleteView):
    model = Plugin

    def form_invalid(self, form):
        return redirect(reverse("plugin_list"))

    def get_success_url(self, **kwargs):
        redirect_url = self.request.POST.get("current_url")

        if redirect_url and url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
            return redirect_url

        return reverse_lazy("plugin_list")


class PluginScheduleView(KATModelPermissionRequiredMixin, UpdateView):
    model = Plugin

    def get_permission_required(self):
        return ["tasks.add_schedule"]  # permission on the Plugin model is added in KATModelPermissionRequiredMixin

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        organization_ids = self.request.POST.getlist("organization")
        action = self.request.POST.get("action", "schedule")

        if action == "cancel":
            if not self.request.user.has_perms(["tasks.delete_schedule"]):
                raise PermissionDenied()
            if organization_ids:
                organizations = Organization.objects.filter(id__in=organization_ids)
                deleted_count = Schedule.objects.filter(plugin=self.object, organization__in=organizations).delete()[0]

                if len(organizations) == 1:
                    messages.success(
                        self.request,
                        _("Plugin '{}' has been unscheduled for organization '{}'.").format(
                            self.object.name, organizations[0].name
                        ),
                    )
                else:
                    messages.success(
                        self.request,
                        _("Plugin '{}' has been unscheduled for {} organizations ({} schedules deleted).").format(
                            self.object.name, len(organizations), deleted_count
                        ),
                    )
            else:
                deleted_count = Schedule.objects.filter(plugin=self.object, organization=None).delete()[0]
                messages.success(
                    self.request,
                    _("Plugin '{}' has been unscheduled globally ({} schedules deleted).").format(
                        self.object.name, deleted_count
                    ),
                )
        elif action == "schedule":
            if not self.request.user.has_perms(["tasks.add_schedule"]):
                raise PermissionDenied()

            if organization_ids:
                # Schedule for specific organizations
                organizations = Organization.objects.filter(id__in=organization_ids)
                for organization in organizations:
                    self.object.schedule_for(organization)

                if len(organizations) == 1:
                    messages.success(
                        self.request,
                        _("Plugin '{}' has been scheduled for organization '{}'.").format(
                            self.object.name, organizations[0].name
                        ),
                    )
                else:
                    messages.success(
                        self.request,
                        _("Plugin '{}' has been scheduled for {} organizations.").format(
                            self.object.name, len(organizations)
                        ),
                    )
            else:
                self.object.schedule()
                messages.success(self.request, _("Plugin '{}' has been scheduled globally.").format(self.object.name))

        return redirect(self.get_success_url())

    def get_success_url(self):
        redirect_url = self.request.POST.get("current_url")

        if redirect_url and url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
            return redirect_url

        return reverse("plugin_detail", kwargs={"pk": self.object.pk})


class BusinessRuleFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(label="Name", lookup_expr="icontains")
    enabled = django_filters.ChoiceFilter(label="State", choices=((True, "Enabled"), (False, "Disabled")))
    object_type = django_filters.ModelChoiceFilter(
        label="Object type", queryset=ContentType.objects.filter(app_label="objects")
    )

    class Meta:
        model = BusinessRule
        fields = ["name", "object_type", "enabled"]


class BusinessRuleListView(FilterView):
    model = BusinessRule
    template_name = "plugins/business_rule_list.html"
    context_object_name = "business_rules"
    filterset_class = BusinessRuleFilter
    paginate_by = 20
    ordering = ["-created_at"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("business_rule_list"), "text": _("Business Rules")}]

        return context


class BusinessRuleDetailView(DetailView):
    model = BusinessRule
    template_name = "plugins/business_rule_detail.html"
    context_object_name = "business_rule"

    object: BusinessRule

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("business_rule_list"), "text": _("Business Rules")}]

        return context


class BusinessRuleForm(forms.ModelForm):
    class Meta:
        model = BusinessRule
        fields = ["name", "description", "enabled"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class BusinessRuleCreateView(KATModelPermissionRequiredMixin, CreateView):
    model = BusinessRule
    form_class = BusinessRuleForm
    template_name = "plugins/business_rule_form.html"

    object: BusinessRule

    def get_success_url(self) -> str:
        return reverse("business_rule_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("business_rule_list"), "text": _("Business Rules")}]

        return context


class BusinessRuleUpdateView(KATModelPermissionRequiredMixin, UpdateView):
    model = BusinessRule
    form_class = BusinessRuleForm
    template_name = "plugins/business_rule_form.html"

    object: BusinessRule

    def get_success_url(self) -> str:
        return reverse("business_rule_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("business_rule_list"), "text": _("Business Rules")}]

        return context


class BusinessRuleDeleteView(KATModelPermissionRequiredMixin, DeleteView):
    model = BusinessRule
    success_url = reverse_lazy("business_rule_list")


class BusinessRuleToggleView(KATModelPermissionRequiredMixin, UpdateView):
    model = BusinessRule
    fields: list[str] = []

    object: BusinessRule

    def form_valid(self, form):
        self.object.enabled = not self.object.enabled
        self.object.save()

        if self.object.enabled:
            messages.success(self.request, _("Business rule '{}' has been enabled.").format(self.object.name))
        else:
            messages.success(self.request, _("Business rule '{}' has been disabled.").format(self.object.name))

        return redirect(self.get_success_url())

    def get_success_url(self):
        redirect_url = self.request.POST.get("current_url")

        if redirect_url and url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
            return redirect_url

        return reverse_lazy("business_rule_list")
