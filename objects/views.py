import contextlib
import csv
import io
import ipaddress
from typing import TYPE_CHECKING, cast

import django_filters
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db.models import Model, OuterRef, Q, QuerySet, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView
from django_filters.views import FilterView
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search

from objects.forms import (
    GenericAssetBulkCreateForm,
    GenericAssetCSVUploadForm,
    HostnameCSVUploadForm,
    IPAddressCSVUploadForm,
)
from objects.models import (
    Finding,
    Hostname,
    IPAddress,
    IPPort,
    Network,
    NoOrgQLSchema,
    ScanLevelEnum,
    Software,
    XTDBOrganization,
)
from openkat.mixins import OrganizationFilterMixin, filter_queryset_orgs_for_user
from openkat.models import Organization, User
from openkat.permissions import KATModelPermissionRequiredMixin
from plugins.models import Plugin
from tasks.models import ObjectSet, Task

if TYPE_CHECKING:
    from django.db.models.query import QuerySet


class ObjectScanLevelForm(forms.Form):
    declared = forms.CharField(
        required=True,
        label=_("Origin"),
        widget=forms.RadioSelect(
            choices=[("inherited", "Inherited"), ("declared", "Declared")],
            attrs={"class": "radio-choice", "data-choicegroup": "scan_type_selector"},
        ),
        initial="inherited",
    )

    scan_level = forms.IntegerField(
        required=False,
        label=_("Clearance level"),
        help_text=_("Plugins with a scan level not exceeding this clearance level will be able to scan this object."),
        error_messages={"required": _("Please select a scan level to proceed.")},
        widget=forms.Select(
            choices=ScanLevelEnum.choices,
            attrs={"aria-describedby": _("explanation-scan-level"), "class": "scan_type_selector declared"},
        ),
    )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields["scan_level"].initial = self.instance.scan_level if self.instance.scan_level is not None else ""
            self.fields["declared"].initial = "declared" if self.instance.declared else "inherited"


class BaseScanLevelUpdateView(KATModelPermissionRequiredMixin, FormView):
    form_class = ObjectScanLevelForm
    model: Model
    detail_url_name: str

    def get_success_url(self):
        return reverse(self.detail_url_name, kwargs={"pk": self.kwargs.get("pk")})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.model.objects.get(pk=self.kwargs.get("pk"))
        return kwargs

    def form_valid(self, form):
        obj = self.model.objects.get(pk=self.kwargs.get("pk"))
        obj.scan_level = None if form.cleaned_data["declared"] == "inherited" else int(form.cleaned_data["scan_level"])
        obj.declared = form.cleaned_data["declared"] == "declared"
        obj.save()

        messages.success(self.request, _("Scan level updated successfully"))
        return super().form_valid(form)


class NetworkFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(label="Name", lookup_expr="icontains")

    class Meta:
        model = Network
        fields = ["name"]


class NetworkListView(OrganizationFilterMixin, FilterView):
    model = Network
    template_name = "objects/network_list.html"
    context_object_name = "networks"
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    filterset_class = NetworkFilter
    ordering = ["-_valid_from"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("objects:network_list"), "text": _("Networks")}]

        return context


class NetworkDetailView(OrganizationFilterMixin, DetailView):
    model = Network
    template_name = "objects/network_detail.html"
    context_object_name = "network"
    object: Network

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        organization_ids = self.request.GET.getlist("organization")
        breadcrumb_url = reverse("objects:network_list")
        if organization_ids:
            breadcrumb_url += "?" + "&".join([f"organization={org_id}" for org_id in organization_ids])

        context["breadcrumbs"] = [{"url": breadcrumb_url, "text": _("Networks")}]
        context["all_organizations"] = Organization.objects.all()

        return context


class NetworkCreateView(KATModelPermissionRequiredMixin, CreateView):
    model = Network
    template_name = "objects/generic_object_form.html"
    fields = ["name", "organizations"]
    success_url = reverse_lazy("objects:network_list")


class NetworkDeleteView(KATModelPermissionRequiredMixin, DeleteView):
    model = Network
    success_url = reverse_lazy("objects:network_list")

    def form_invalid(self, form):
        return redirect(reverse("objects:network_list"))


class NetworkScanLevelUpdateView(BaseScanLevelUpdateView):
    model = Network
    detail_url_name = "objects:network_detail"

    def get_permission_required(self):
        return ["objects.change_network", "openkat.can_set_clearance_level"]


class NetworkManageOrganizationsView(KATModelPermissionRequiredMixin, FormView):
    http_method_names = ["post"]

    def get_permission_required(self):
        return ["objects.change_network", "openkat.change_organization", "objects.change_networkorganization"]

    def post(self, request, *args, **kwargs):
        network = Network.objects.get(pk=self.kwargs.get("pk"))
        organization_ids = request.POST.getlist("organizations")

        if organization_ids:
            organizations = XTDBOrganization.objects.filter(pk__in=organization_ids)
            network.organizations.set(organizations)
            messages.success(request, _("Organizations updated successfully."))
        else:
            network.organizations.clear()
            messages.success(request, _("All organizations removed."))

        return redirect(reverse("objects:network_detail", kwargs={"pk": network.pk}))


class IPAddressManageOrganizationsView(KATModelPermissionRequiredMixin, FormView):
    http_method_names = ["post"]

    def get_permission_required(self):
        return ["objects.change_ipaddress", "openkat.change_organization", "objects.change_ipaddressorganization"]

    def post(self, request, *args, **kwargs):
        ipaddress = IPAddress.objects.get(pk=self.kwargs.get("pk"))
        organization_ids = request.POST.getlist("organizations")

        if organization_ids:
            organizations = XTDBOrganization.objects.filter(pk__in=organization_ids)
            ipaddress.organizations.set(organizations)
            messages.success(request, _("Organizations updated successfully."))
        else:
            ipaddress.organizations.clear()
            messages.success(request, _("All organizations removed."))

        return redirect(reverse("objects:ipaddress_detail", kwargs={"pk": ipaddress.pk}))


class HostnameManageOrganizationsView(KATModelPermissionRequiredMixin, FormView):
    http_method_names = ["post"]

    def get_permission_required(self):
        return ["objects.change_hostname", "openkat.change_organization", "objects.change_hostnameorganization"]

    def post(self, request, *args, **kwargs):
        hostname = Hostname.objects.get(pk=self.kwargs.get("pk"))
        organization_ids = request.POST.getlist("organizations")

        if organization_ids:
            organizations = XTDBOrganization.objects.filter(pk__in=organization_ids)
            hostname.organizations.set(organizations)
            messages.success(request, _("Organizations updated successfully."))
        else:
            hostname.organizations.clear()
            messages.success(request, _("All organizations removed."))

        return redirect(reverse("objects:hostname_detail", kwargs={"pk": hostname.pk}))


class FindingFilter(django_filters.FilterSet):
    finding_type__code = django_filters.CharFilter(label="Finding type", lookup_expr="icontains")
    object_search = django_filters.CharFilter(label="Object", method="filter_object_search")
    score = django_filters.NumberFilter(label="Minimum Risk Score", field_name="finding_type__score", lookup_expr="gte")

    class Meta:
        model = Finding
        fields = ["finding_type__code", "object_search", "score"]

    def filter_object_search(self, queryset, name, value):
        if not value:
            return queryset

        return queryset.filter(Q(hostname__name__icontains=value) | Q(ip_address__ip_address__icontains=value))


class FindingListView(OrganizationFilterMixin, FilterView):
    model = Finding
    template_name = "objects/finding_list.html"
    context_object_name = "findings"
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    filterset_class = FindingFilter
    ordering = ["-_valid_from"]

    def get_queryset(self) -> "QuerySet[Finding]":
        queryset = super().get_queryset().prefetch_related("finding_type")

        order_by = self.request.GET.get("order_by", "_valid_from")
        sorting_order = self.request.GET.get("sorting_order", "desc")

        if order_by and sorting_order == "desc":
            return queryset.order_by(f"-{order_by}")

        return queryset.order_by(order_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("objects:finding_list"), "text": _("Findings")}]
        context["order_by"] = self.request.GET.get("order_by")
        context["sorting_order"] = self.request.GET.get("sorting_order", "asc")
        context["sorting_order_class"] = "ascending" if context["sorting_order"] == "asc" else "descending"
        context["columns"] = [
            {"field": "", "label": "Severity", "sortable": False},
            {"field": "", "label": "Finding type", "sortable": False},
            {"field": "", "label": "Object", "sortable": False},
            {"field": "", "label": "Risc score", "sortable": False},
            {"field": "_valid_from", "label": "Last seen", "sortable": True},
        ]
        if self.request.user.has_perm("objects.delete_finding"):
            context["columns"].append({"field": "", "label": "Delete", "sortable": False})
        context["columns"].append({"field": "", "label": "", "sortable": False})

        return context


class FindingCreateView(KATModelPermissionRequiredMixin, CreateView):
    model = Finding
    template_name = "objects/generic_object_form.html"
    fields = ["finding_type", "hostname", "ip_address"]
    success_url = reverse_lazy("objects:finding_list")


class FindingDeleteView(KATModelPermissionRequiredMixin, DeleteView):
    model = Finding
    success_url = reverse_lazy("objects:finding_list")

    def form_invalid(self, form):
        return redirect(reverse("objects:finding_list"))


class ScanLevelFilterMixin:
    object_set = django_filters.ModelChoiceFilter(
        label="Object set", queryset=ObjectSet.objects.none(), empty_label="All objects", method="filter_by_object_set"
    )
    scan_level = django_filters.MultipleChoiceFilter(
        label="Scan level",
        choices=list(ScanLevelEnum.choices) + [("none", "None")],
        method="filter_by_scan_level",
        widget=forms.CheckboxSelectMultiple(attrs={"class": "scan-level-filter-checkboxes"}),
    )
    declared = django_filters.BooleanFilter(label="Declared")

    def filter_by_object_set(self, queryset, name, value):
        return queryset

    def filter_by_scan_level(self, queryset, name, value):
        if not value:
            return queryset

        q_objects = Q()

        for level in value:
            if level == "none":
                q_objects |= Q(scan_level__isnull=True)
            else:
                q_objects |= Q(scan_level=level)

        return queryset.filter(q_objects)


class IPAddressFilter(ScanLevelFilterMixin, django_filters.FilterSet):
    ip_address = django_filters.CharFilter(label="Address", lookup_expr="icontains")
    query = django_filters.CharFilter(label="Query", method="filter_by_query")
    object_set = ScanLevelFilterMixin.object_set  # Redefined because else django filter doesn't understand
    scan_level = ScanLevelFilterMixin.scan_level  # Redefined because else django filter doesn't understand
    declared = ScanLevelFilterMixin.declared  # Redefined because else django filter doesn't understand

    class Meta:
        model = IPAddress
        fields = ["ip_address", "object_set", "query", "declared", "scan_level"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ipaddress_ct = ContentType.objects.get_for_model(IPAddress)
        queryset = ObjectSet.objects.filter(object_type=ipaddress_ct)
        if queryset.exists():
            self.filters["object_set"].queryset = queryset
        else:
            del self.filters["object_set"]

    def filter_by_query(self, queryset, name, value):
        if not value:
            return queryset

        try:
            return apply_search(queryset, value, NoOrgQLSchema)
        except DjangoQLError as e:
            messages.warning(self.request, f"DjangoQL query invalid: {e}")
            return queryset


class IPAddressListView(OrganizationFilterMixin, FilterView):
    model = IPAddress
    template_name = "objects/ipaddress_list.html"
    context_object_name = "ipaddresses"
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    filterset_class = IPAddressFilter
    ordering = ["-_valid_from"]
    http_method_names = ["get", "post"]

    def get_queryset(self) -> "QuerySet[IPAddress]":
        queryset = super().get_queryset()
        object_set_id = self.request.GET.get("object_set")
        if object_set_id:
            queryset = ObjectSet.objects.get(
                id=object_set_id, object_type=ContentType.objects.get_for_model(IPAddress)
            ).get_query_objects(queryset)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("objects:ipaddress_list"), "text": _("IPAddresses")}]

        object_set_id = self.request.GET.get("object_set")
        if object_set_id:
            obj_set = ObjectSet.objects.get(id=object_set_id, object_type=ContentType.objects.get_for_model(IPAddress))
            if obj_set.static_objects:
                messages.warning(
                    self.request,
                    _('"{}" has fixed objects that are ignored (only query results are shown).').format(obj_set.name),
                )

        ipaddress_ct = ContentType.objects.get_for_model(IPAddress)
        context["object_sets"] = ObjectSet.objects.filter(object_type=ipaddress_ct)
        context["scan_levels"] = ScanLevelEnum
        context["plugins"] = Plugin.objects.filter(consumes__contains=["IPAddress"])
        context["scan_level_form"] = ObjectScanLevelForm

        return context

    def post(self, request, *args, **kwargs):
        action_type = request.POST.get("action")
        selected_ids = request.POST.getlist("ipaddress")

        if not selected_ids:
            messages.warning(request, _("No IP addresses selected."))
            return redirect(reverse("objects:ipaddress_list"))

        if action_type == "scan":
            url = reverse("add_task") + "?" + "&".join([f"input_ips={selected}" for selected in selected_ids])
            return redirect(url)
        elif action_type == "create-object-set":
            ipaddress_ct = ContentType.objects.get_for_model(IPAddress)
            url = (
                reverse("add_object_set")
                + f"?object_type={ipaddress_ct.pk}&"
                + "&".join([f"objects={selected}" for selected in selected_ids])
            )
            return redirect(url)
        elif action_type == "set-scan-level":
            if not self.request.user.has_perms(["objects.change_ipaddress", "objects.can_set_clearance_level"]):
                raise PermissionDenied()

            scan_level = request.POST.get("scan_level")
            scan_type = request.POST.get("declared")
            if scan_type == "inherited":
                updated_count = IPAddress.objects.filter(pk__in=selected_ids).update(scan_level=None, declared=False)
                messages.success(request, _("Removed scan level for {} IP addresses.").format(updated_count))
            elif scan_type == "declared" and scan_level:
                updated_count = IPAddress.objects.filter(pk__in=selected_ids).update(
                    scan_level=int(scan_level), declared=True
                )
                messages.success(request, _("Updated scan level for {} IP addresses.").format(updated_count))
            else:
                messages.warning(request, _("No scan level selected."))
        elif action_type == "delete":
            if not self.request.user.has_perms(["objects.delete_ipaddress"]):
                raise PermissionDenied()
            try:
                IPAddress.objects.filter(pk__in=selected_ids).delete()
                messages.success(request, _("Deleted {} IP addresses.").format(len(selected_ids)))
            except DatabaseError:
                messages.warning(request, _("Failed to delete IP addresses."))

        return redirect(reverse("objects:ipaddress_list"))


class IPAddressDetailView(OrganizationFilterMixin, DetailView):
    model = IPAddress
    template_name = "objects/ipaddress_detail.html"
    context_object_name = "ipaddress"
    object: IPAddress

    def get_queryset(self) -> "QuerySet[IPAddress]":
        return IPAddress.objects.prefetch_related("ipport_set")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        organization_ids = self.request.GET.getlist("organization")
        breadcrumb_url = reverse("objects:ipaddress_list")
        if organization_ids:
            breadcrumb_url += "?" + "&".join([f"organization={org_id}" for org_id in organization_ids])

        context["breadcrumbs"] = [{"url": breadcrumb_url, "text": _("IPAddresses")}]
        context["findings"] = Finding.objects.filter(ip_address=self.object)
        context["scan_level_form"] = ObjectScanLevelForm(instance=self.object)
        context["all_organizations"] = Organization.objects.all()

        return context


class IPAddressScanLevelDetailView(OrganizationFilterMixin, DetailView):
    model = IPAddress
    template_name = "objects/ipaddress_detail_scan_level.html"
    context_object_name = "ipaddress"
    object: IPAddress

    def get_queryset(self) -> "QuerySet[IPAddress]":
        return IPAddress.objects.prefetch_related("ipport_set")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        organization_ids = self.request.GET.getlist("organization")
        breadcrumb_url = reverse("objects:ipaddress_list")
        if organization_ids:
            breadcrumb_url += "?" + "&".join([f"organization={org_id}" for org_id in organization_ids])

        context["breadcrumbs"] = [{"url": breadcrumb_url, "text": _("IPAddresses")}]
        context["scan_level_form"] = ObjectScanLevelForm(instance=self.object)

        return context


class IPAddressTasksDetailView(OrganizationFilterMixin, ListView):
    model = Task
    template_name = "objects/ipaddress_detail_tasks.html"
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    ordering = ["-created_at"]

    def get_queryset(self) -> "QuerySet[Task]":
        ipaddress = IPAddress.objects.get(pk=self.kwargs.get("pk"))
        qs = Task.objects.filter(data__input_data__has_any_keys=[str(ipaddress.ip_address)]).annotate(
            plugin_name=Subquery(
                Plugin.objects.filter(plugin_id=KeyTextTransform("plugin_id", OuterRef("data"))).values("name")
            )
        )
        return filter_queryset_orgs_for_user(
            qs, self.request.user, {int(org_id) for org_id in self.request.GET.getlist("organization")}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ipaddress = IPAddress.objects.get(pk=self.kwargs.get("pk"))
        context["ipaddress"] = ipaddress

        organization_ids = self.request.GET.getlist("organization")
        breadcrumb_url = reverse("objects:ipaddress_list")
        if organization_ids:
            breadcrumb_url += "?" + "&".join([f"organization={org_id}" for org_id in organization_ids])

        context["breadcrumbs"] = [{"url": breadcrumb_url, "text": _("IPAddresses")}]

        return context


class IPAddressCreateView(KATModelPermissionRequiredMixin, CreateView):
    model = IPAddress
    template_name = "objects/ipaddress_create.html"
    fields = ["network", "ip_address", "organizations"]
    success_url = reverse_lazy("objects:ipaddress_list")

    def get_initial(self):
        initial = super().get_initial()
        with contextlib.suppress(Network.DoesNotExist):
            initial["network"] = Network.objects.get(name="internet")
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["csv_form"] = IPAddressCSVUploadForm()
        context["csv_upload_url"] = reverse_lazy("objects:ipaddress_csv_upload")
        return context


class IPAddressCSVUploadView(KATModelPermissionRequiredMixin, FormView):
    template_name = "objects/ipaddress_create.html"
    form_class = IPAddressCSVUploadForm
    success_url = reverse_lazy("objects:ipaddress_list")
    permission_required = "objects.add_ipaddress"

    def form_valid(self, form):
        network = form.cleaned_data.get("network")

        if not network:
            network, created = Network.objects.get_or_create(name="internet")

        csv_data = io.StringIO(form.cleaned_data["csv_file"].read().decode("UTF-8"))

        created_count = 0
        error_count = 0
        skipped_count = 0
        organizations_set = 0

        try:
            reader = csv.reader(csv_data, delimiter=",", quotechar='"')
            for row_num, row in enumerate(reader, 1):
                if not row or not row[0].strip():
                    continue

                address = row[0].strip()
                org_id = None

                # Parse optional organization id from column 2
                if len(row) >= 2 and row[1].strip():
                    org_id = row[1].strip()

                try:
                    ipaddress, created = IPAddress.objects.get_or_create(network=network, ip_address=address)

                    # Handle organization assignment
                    if org_id:
                        org = _get_organization(org_id, self.request)
                        if org:
                            xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
                            ipaddress.organizations.set([xtdb_org])
                            organizations_set += 1

                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    error_count += 1
                    messages.warning(
                        self.request,
                        _("Error creating IP address '{address}' on row {row_num}: {error}").format(
                            address=address, row_num=row_num, error=str(e)
                        ),
                    )

            if created_count > 0:
                messages.success(
                    self.request, _("Successfully created {count} IP addresses.").format(count=created_count)
                )
            if skipped_count > 0:
                messages.info(self.request, _("{count} IP addresses already existed.").format(count=skipped_count))
            if organizations_set > 0:
                messages.success(
                    self.request,
                    _("Successfully set organizations for {count} IP addresses.").format(count=organizations_set),
                )
            if error_count > 0:
                messages.warning(
                    self.request, _("{count} IP addresses had errors and were not created.").format(count=error_count)
                )

        except csv.Error as e:
            messages.error(self.request, _("Error parsing CSV file: {error}").format(error=str(e)))

        return super().form_valid(form)


class IPAddressDeleteView(KATModelPermissionRequiredMixin, DeleteView):
    model = IPAddress
    success_url = reverse_lazy("objects:ipaddress_list")

    def form_invalid(self, form):
        return redirect(reverse("objects:ipaddress_list"))


class IPAddressScanLevelUpdateView(BaseScanLevelUpdateView):
    model = IPAddress
    detail_url_name = "objects:ipaddress_scan_level_detail"

    def get_permission_required(self):
        return ["objects.change_ipaddress", "objects.can_set_clearance_level"]


class HostnameFilter(ScanLevelFilterMixin, django_filters.FilterSet):
    name = django_filters.CharFilter(label="Hostname", lookup_expr="icontains")
    query = django_filters.CharFilter(label="Query", method="filter_by_query")
    declared = ScanLevelFilterMixin.declared  # Redefined because else django filter doesn't understand
    scan_level = ScanLevelFilterMixin.scan_level  # Redefined because else django filter doesn't understand
    object_set = ScanLevelFilterMixin.object_set  # Redefined because else django filter doesn't understand

    class Meta:
        model = Hostname
        fields = ["name", "object_set", "query", "declared", "scan_level"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = ObjectSet.objects.filter(object_type=ContentType.objects.get_for_model(Hostname))
        if queryset.exists():
            self.filters["object_set"].queryset = queryset
        else:
            del self.filters["object_set"]

    def filter_by_query(self, queryset, name, value):
        if not value:
            return queryset

        try:
            return apply_search(queryset, value, NoOrgQLSchema)
        except DjangoQLError as e:
            messages.warning(self.request, f"DjangoQL query invalid: {e}")
            return queryset


class HostnameListView(OrganizationFilterMixin, FilterView):
    model = Hostname
    template_name = "objects/hostname_list.html"
    context_object_name = "hostnames"
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    filterset_class = HostnameFilter
    ordering = ["-_valid_from"]
    http_method_names = ["get", "post"]

    def get_queryset(self) -> "QuerySet[Hostname]":
        queryset = super().get_queryset()

        object_set_id = self.request.GET.get("object_set")
        if object_set_id:
            queryset = ObjectSet.objects.get(
                id=object_set_id, object_type=ContentType.objects.get_for_model(Hostname)
            ).get_query_objects(queryset)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("objects:hostname_list"), "text": _("Hostnames")}]

        object_set_id = self.request.GET.get("object_set")
        if object_set_id:
            obj_set = ObjectSet.objects.get(id=object_set_id, object_type=ContentType.objects.get_for_model(Hostname))
            if obj_set.static_objects:
                messages.warning(
                    self.request,
                    _('"{}" has static objects that are ignored. Only the query is applied.').format(obj_set.name),
                )

        context["object_sets"] = ObjectSet.objects.filter(object_type=ContentType.objects.get_for_model(Hostname))
        context["scan_levels"] = ScanLevelEnum
        context["plugins"] = Plugin.objects.filter(consumes__contains=["Hostname"])
        context["scan_level_form"] = ObjectScanLevelForm

        return context

    def post(self, request, *args, **kwargs):
        action_type = request.POST.get("action")
        selected = request.POST.getlist("hostname")

        if not selected:
            messages.warning(request, _("No hostnames selected."))
            return redirect(reverse("objects:hostname_list"))

        if action_type == "scan":
            url = reverse("add_task") + "?" + "&".join([f"input_hostnames={selected}" for selected in selected])
            return redirect(url)
        elif action_type == "create-object-set":
            ct = ContentType.objects.get_for_model(Hostname)
            url = (
                reverse("add_object_set") + f"?object_type={ct.pk}&" + "&".join([f"objects={_id}" for _id in selected])
            )
            return redirect(url)
        elif action_type == "set-scan-level":
            if not self.request.user.has_perms(["objects.change_hostname", "objects.can_set_clearance_level"]):
                raise PermissionDenied()

            scan_level = self.request.POST.get("scan_level")
            scan_type = self.request.POST.get("declared")

            if scan_type == "inherited":
                Hostname.objects.filter(pk__in=selected).update(scan_level=None, declared=False)
                messages.success(request, _("Removed scan level."))
            elif scan_type == "declared" and scan_level:
                Hostname.objects.filter(pk__in=selected).update(scan_level=int(scan_level), declared=True)
                messages.success(request, _("Updated scan level."))
            else:
                messages.warning(request, _("No scan level selected."))
        elif action_type == "delete":
            if not self.request.user.has_perms(["objects.delete_hostname"]):
                raise PermissionDenied()
            try:
                Hostname.objects.filter(pk__in=selected).delete()
                messages.success(request, _("Deleted {} hostnames.").format(len(selected)))
            except DatabaseError:
                messages.warning(request, _("No plugin selected."))

        return redirect(reverse("objects:hostname_list"))


class HostnameDetailView(OrganizationFilterMixin, DetailView):
    model = Hostname
    template_name = "objects/hostname_detail.html"
    context_object_name = "hostname"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization_ids = self.request.GET.getlist("organization")
        breadcrumb_url = reverse("objects:hostname_list")
        if organization_ids:
            breadcrumb_url += "?" + "&".join([f"organization={org_id}" for org_id in organization_ids])

        context["breadcrumbs"] = [{"url": breadcrumb_url, "text": _("Hostnames")}]

        context["dnsarecord_set"] = self.object.dnsarecord_set.all()
        context["dnsaaaarecord_set"] = self.object.dnsaaaarecord_set.all()
        context["dnscnamerecord_set"] = self.object.dnscnamerecord_set.all()
        context["dnsmxrecord_set"] = self.object.dnsmxrecord_set.all()
        context["dnsnsrecord_set"] = self.object.dnsnsrecord_set.all()
        context["dnsptrrecord_set"] = self.object.dnsptrrecord_set.all()
        context["dnscaarecord_set"] = self.object.dnscaarecord_set.all()
        context["dnstxtrecord_set"] = self.object.dnstxtrecord_set.all()
        context["dnssrvrecord_set"] = self.object.dnssrvrecord_set.all()

        context["dnscnamerecord_target_set"] = self.object.dnscnamerecord_target_set.all()
        context["dnsmxrecord_mailserver"] = self.object.dnsmxrecord_mailserver.all()
        context["dnsnsrecord_nameserver"] = self.object.dnsnsrecord_nameserver.all()
        context["findings"] = Finding.objects.filter(hostname=self.object)
        context["scan_level_form"] = ObjectScanLevelForm(instance=self.object)
        context["all_organizations"] = Organization.objects.all()

        return context


class HostnameScanLevelDetailView(OrganizationFilterMixin, DetailView):
    model = Hostname
    template_name = "objects/hostname_detail_scan_level.html"
    context_object_name = "hostname"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        organization_ids = self.request.GET.getlist("organization")
        breadcrumb_url = reverse("objects:hostname_list")
        if organization_ids:
            breadcrumb_url += "?" + "&".join([f"organization={org_id}" for org_id in organization_ids])

        context["breadcrumbs"] = [{"url": breadcrumb_url, "text": _("Hostnames")}]
        context["scan_level_form"] = ObjectScanLevelForm(instance=self.object)

        return context


class HostnameTasksDetailView(OrganizationFilterMixin, ListView):
    model = Task
    template_name = "objects/hostname_detail_tasks.html"
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    ordering = ["-created_at"]

    def get_queryset(self) -> "QuerySet[Task]":
        hostname = Hostname.objects.get(pk=self.kwargs.get("pk"))
        qs = Task.objects.filter(data__input_data__has_any_keys=[str(hostname.name)]).annotate(
            plugin_name=Subquery(
                Plugin.objects.filter(plugin_id=KeyTextTransform("plugin_id", OuterRef("data"))).values("name")
            )
        )

        user = cast("User", self.request.user)
        return filter_queryset_orgs_for_user(
            qs, user, {int(org_id) for org_id in self.request.GET.getlist("organization")}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hostname"] = Hostname.objects.get(pk=self.kwargs.get("pk"))
        organization_ids = self.request.GET.getlist("organization")
        breadcrumb_url = reverse("objects:hostname_list")

        if organization_ids:
            breadcrumb_url += "?" + "&".join([f"organization={org_id}" for org_id in organization_ids])

        context["breadcrumbs"] = [{"url": breadcrumb_url, "text": _("Hostnames")}]

        return context


class HostnameScanLevelUpdateView(BaseScanLevelUpdateView):
    model = Hostname
    detail_url_name = "objects:hostname_scan_level_detail"

    def get_permission_required(self):
        return ["objects.change_hostname", "objects.can_set_clearance_level"]


class HostnameDeleteView(KATModelPermissionRequiredMixin, DeleteView):
    model = Hostname
    success_url = reverse_lazy("objects:hostname_list")

    def form_invalid(self, form):
        return redirect(reverse("objects:hostname_list"))


class HostnameCreateView(KATModelPermissionRequiredMixin, CreateView):
    model = Hostname
    template_name = "objects/hostname_create.html"
    fields = ["network", "name", "organizations"]
    success_url = reverse_lazy("objects:hostname_list")

    def get_initial(self):
        initial = super().get_initial()
        with contextlib.suppress(Network.DoesNotExist):
            initial["network"] = Network.objects.get(name="internet")
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["csv_form"] = HostnameCSVUploadForm()
        context["csv_upload_url"] = reverse_lazy("objects:hostname_csv_upload")
        return context


def _get_organization(org_id: str | None, request: HttpRequest) -> Organization | None:
    if not org_id:
        return None

    try:
        return Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        messages.warning(
            request,
            _("Organization with id '{org_id}' not found. Skipping scan level for this row.").format(org_id=org_id),
        )
        return None


class HostnameCSVUploadView(KATModelPermissionRequiredMixin, FormView):
    template_name = "objects/hostname_create.html"
    form_class = HostnameCSVUploadForm
    success_url = reverse_lazy("objects:hostname_list")
    permission_required = "objects.add_hostname"

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        network = form.cleaned_data.get("network")

        if not network:
            network, created = Network.objects.get_or_create(name="internet")

        csv_data = io.StringIO(csv_file.read().decode("UTF-8"))

        created_count = 0
        error_count = 0
        skipped_count = 0
        organizations_set = 0

        try:
            reader = csv.reader(csv_data, delimiter=",", quotechar='"')
            for row_num, row in enumerate(reader, 1):
                if not row or not row[0].strip():
                    continue  # Skip empty rows

                name = row[0].strip()
                org_id = None

                # Parse optional organization id from column 2
                if len(row) >= 2 and row[1].strip():
                    org_id = row[1].strip()

                try:
                    hostname, created = Hostname.objects.get_or_create(network=network, name=name)

                    # Handle organization assignment
                    if org_id:
                        org = _get_organization(org_id, self.request)
                        if org:
                            hostname.organizations.set([XTDBOrganization.objects.get(pk=org.pk)])
                            organizations_set += 1

                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    error_count += 1
                    messages.warning(
                        self.request,
                        _("Error creating hostname '{name}' on row {row}: {er}").format(
                            name=name, row=row_num, er=str(e)
                        ),
                    )

            messages.success(self.request, _("Successfully created {count} hostnames.").format(count=created_count))
            messages.info(self.request, _("{count} hostnames already existed.").format(count=skipped_count))
            messages.success(
                self.request, _("Successfully set organizations for {count} hostnames.").format(count=organizations_set)
            )
            messages.warning(self.request, _("{count} hostnames were not created.").format(count=error_count))
        except csv.Error as e:
            messages.error(self.request, _("Error parsing CSV file: {error}").format(error=str(e)))

        return super().form_valid(form)


class IPPortDeleteView(KATModelPermissionRequiredMixin, DeleteView):
    model = IPPort

    def get_success_url(self) -> str:
        return reverse("objects:ipaddress_detail", kwargs={"pk": self.object.ip_address_id})


class IPPortSoftwareDeleteView(KATModelPermissionRequiredMixin, DeleteView):
    model = Software
    http_method_names = ["post"]

    def form_valid(self, form):
        try:
            IPPort.objects.get(pk=self.kwargs.get("port_pk")).software.remove(self.get_object())
            return redirect(self.get_success_url())
        except IPPort.DoesNotExist:
            return redirect(reverse("objects:ipaddress_list"))

    def get_success_url(self) -> str:
        try:
            port = IPPort.objects.get(pk=self.kwargs.get("port_pk"))
            return reverse("objects:ipaddress_detail", kwargs={"pk": port.ip_address_id})
        except IPPort.DoesNotExist:
            return reverse("objects:ipaddress_list")


def is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


class GenericAssetCreateView(KATModelPermissionRequiredMixin, FormView):
    template_name = "objects/generic_asset_create.html"
    form_class = GenericAssetBulkCreateForm
    success_url = reverse_lazy("objects:generic_asset_create")

    def get_permission_required(self):
        return ["objects.add_ipaddress", "objects.add_hostname"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["csv_form"] = GenericAssetCSVUploadForm()
        context["csv_upload_url"] = reverse_lazy("objects:generic_asset_csv_upload")
        return context

    def form_valid(self, form):
        assets = form.cleaned_data["assets"]
        network = form.cleaned_data.get("network")
        organizations = form.cleaned_data.get("organizations")

        if not network:
            network, created = Network.objects.get_or_create(name="internet")

        ip_created = 0
        ip_skipped = 0
        hostname_created = 0
        hostname_skipped = 0
        error_count = 0

        for line_num, asset in enumerate(assets, 1):
            asset = asset.strip()
            if not asset:
                continue

            try:
                if is_valid_ip(asset):
                    ipaddress, created = IPAddress.objects.get_or_create(network=network, ip_address=asset)
                    if organizations:
                        ipaddress.organizations.set(organizations)
                    if created:
                        ip_created += 1
                    else:
                        ip_skipped += 1
                else:
                    hostname, created = Hostname.objects.get_or_create(network=network, name=asset.lower())
                    if organizations:
                        hostname.organizations.set(organizations)
                    if created:
                        hostname_created += 1
                    else:
                        hostname_skipped += 1
            except Exception as e:
                error_count += 1
                messages.warning(
                    self.request,
                    _("Error creating asset '{asset}' on line {line_num}: {error}").format(
                        asset=asset, line_num=line_num, error=str(e)
                    ),
                )

        messages.success(self.request, _("Successfully created {count} IP addresses.").format(count=ip_created))
        messages.success(self.request, _("Successfully created {count} hostnames.").format(count=hostname_created))
        messages.info(self.request, _("{count} IP addresses already existed.").format(count=ip_skipped))
        messages.info(self.request, _("{count} hostnames already existed.").format(count=hostname_skipped))

        if error_count > 0:
            messages.warning(
                self.request, _("{count} assets had errors and were not created.").format(count=error_count)
            )

        return super().form_valid(form)


class GenericAssetCSVUploadView(KATModelPermissionRequiredMixin, FormView):
    template_name = "objects/generic_asset_csv_upload.html"
    form_class = GenericAssetCSVUploadForm
    success_url = reverse_lazy("objects:generic_asset_create")

    def get_permission_required(self):
        return ["objects.add_ipaddress", "objects.add_hostname"]

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        default_network = form.cleaned_data.get("network")
        default_organizations = form.cleaned_data.get("organizations")

        if not default_network:
            default_network, created = Network.objects.get_or_create(name="internet")

        csv_data = io.StringIO(csv_file.read().decode("UTF-8"))

        ip_created = 0
        ip_skipped = 0
        hostname_created = 0
        hostname_skipped = 0
        error_count = 0
        scan_levels_set = 0
        organizations_set = 0

        try:
            reader = csv.reader(csv_data, delimiter=",", quotechar='"')
            for row_num, row in enumerate(reader, 1):
                if not row or not row[0].strip():
                    continue  # Skip empty rows

                asset = row[0].strip()
                scan_level_value = None
                org_id = None

                # Parse optional columns
                if len(row) >= 2 and row[1].strip():
                    try:
                        scan_level_value = int(row[1].strip())
                        if scan_level_value < 0 or scan_level_value > 4:
                            messages.warning(
                                self.request,
                                _(
                                    "Row {row_num}: Invalid scan level {level}. Must be 0-4. Skipping scan level."
                                ).format(row_num=row_num, level=scan_level_value),
                            )
                            scan_level_value = None
                    except ValueError:
                        messages.warning(
                            self.request,
                            _(
                                "Row {row_num}: Invalid scan level '{value}'. Must be an integer. Skipping scan level."
                            ).format(row_num=row_num, value=row[1].strip()),
                        )

                # Parse organization id from column 3
                if len(row) >= 3 and row[2].strip():
                    org_id = row[2].strip()

                try:
                    if is_valid_ip(asset):
                        ipaddress_obj, created = IPAddress.objects.get_or_create(
                            network=default_network, ip_address=asset
                        )
                        if created:
                            ip_created += 1
                        else:
                            ip_skipped += 1

                        if scan_level_value is not None:
                            ipaddress_obj.scan_level = scan_level_value
                            ipaddress_obj.declared = True
                            ipaddress_obj.save()
                            scan_levels_set += 1

                        # Handle organization assignment
                        organizations_to_set = []
                        if org_id:
                            org = _get_organization(org_id, self.request)
                            if org:
                                xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
                                organizations_to_set = [xtdb_org]
                        elif default_organizations:
                            organizations_to_set = list(default_organizations)

                        if organizations_to_set:
                            ipaddress_obj.organizations.set(organizations_to_set)
                            organizations_set += 1
                    else:
                        hostname_obj, created = Hostname.objects.get_or_create(
                            network=default_network, name=asset.lower()
                        )
                        if created:
                            hostname_created += 1
                        else:
                            hostname_skipped += 1

                        if scan_level_value is not None:
                            hostname_obj.scan_level = scan_level_value
                            hostname_obj.declared = True
                            hostname_obj.save()
                            scan_levels_set += 1

                        organizations_to_set = []
                        if org_id:
                            org = _get_organization(org_id, self.request)
                            if org:
                                organizations_to_set = [XTDBOrganization.objects.get(pk=org.pk)]
                        elif default_organizations:
                            organizations_to_set = list(default_organizations)

                        if organizations_to_set:
                            hostname_obj.organizations.set(organizations_to_set)
                            organizations_set += 1

                except Exception as e:
                    error_count += 1
                    messages.warning(
                        self.request,
                        _("Error creating asset '{asset}' on row {row_num}: {error}").format(
                            asset=asset, row_num=row_num, error=str(e)
                        ),
                    )

            messages.success(self.request, _("Successfully created {count} IP addresses.").format(count=ip_created))
            messages.success(self.request, _("Successfully created {count} hostnames.").format(count=hostname_created))
            messages.info(self.request, _("{count} IP addresses already existed.").format(count=ip_skipped))
            messages.info(self.request, _("{count} hostnames already existed.").format(count=hostname_skipped))
            messages.success(
                self.request, _("Successfully set scan levels for {count} assets.").format(count=scan_levels_set)
            )
            messages.success(
                self.request, _("Successfully set organizations for {count} assets.").format(count=organizations_set)
            )

            if error_count > 0:
                messages.warning(
                    self.request, _("{count} assets had errors and were not created.").format(count=error_count)
                )

        except csv.Error as e:
            messages.error(self.request, _("Error parsing CSV file: {error}").format(error=str(e)))

        return super().form_valid(form)
