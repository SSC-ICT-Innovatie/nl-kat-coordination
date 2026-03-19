import json
from json import JSONDecodeError

import tagulous.admin
from crisis_room.models import Dashboard, DashboardItem
from django.contrib import admin, messages
from django.db.models import JSONField
from django.forms import widgets
from django.http import HttpRequest, HttpResponseRedirect

from rocky.exceptions import RockyError
from tools.models import Indemnification, OOIInformation, Organization, OrganizationMember, OrganizationTag


class JSONInfoWidget(widgets.Textarea):
    # neater way of displaying json field
    def format_value(self, value):
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split("\n")]
            self.attrs["rows"] = min(max(len(row_lengths) + 2, 10), 30)
            self.attrs["cols"] = min(max(max(row_lengths) + 2, 40), 120)
            return value
        except JSONDecodeError:
            return super().format_value(value)


@admin.register(OOIInformation)
class OOIInformationAdmin(admin.ModelAdmin):
    # makes sure that the order stays the same
    fields = ("id", "data", "consult_api")

    # better layout of Json field
    formfield_overrides = {JSONField: {"widget": JSONInfoWidget}}

    # if pk is not readonly, it will create a new record upon editing
    def get_readonly_fields(
        self, request: HttpRequest, obj: OOIInformation | None = None
    ) -> list[str] | tuple[str, ...]:
        if obj is not None:  # editing an existing object
            if not obj.value:
                return self.readonly_fields + ("id", "consult_api")
            return self.readonly_fields + ("id",)
        return self.readonly_fields


class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "tags"]

    def add_view(self, request, *args, **kwargs):
        try:
            return super().add_view(request, *args, **kwargs)
        except RockyError as e:
            self.message_user(request, str(e), level=messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())

    def get_readonly_fields(self, request, obj=None):
        # Obj is None when adding an organization and in that case we don't make
        # code read only so it is possible to specify the code when creating an
        # organization, but code must be read only after the organization
        # objecht has been created.
        if obj:
            return ["code"]
        else:
            return []


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "organization")


@admin.register(Indemnification)
class IndemnificationAdmin(admin.ModelAdmin):
    list_display = ("organization", "user")

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return [f.name for f in self.model._meta.fields]
        else:
            return []


@admin.register(OrganizationTag)
class OrganizationTagAdmin(admin.ModelAdmin):
    pass


@admin.register(DashboardItem)
class DahboardDataAdmin(admin.ModelAdmin):
    pass


@admin.register(Dashboard)
class DahboardAdmin(admin.ModelAdmin):
    pass


tagulous.admin.register(Organization, OrganizationAdmin)
