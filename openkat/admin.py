import tagulous.admin
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

from openkat.exceptions import OpenKATError
from openkat.models import AuthToken, Organization, OrganizationMember, OrganizationTag, User


class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "tags"]

    def add_view(self, request, *args, **kwargs):
        try:
            return super().add_view(request, *args, **kwargs)
        except OpenKATError as e:
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


@admin.register(OrganizationTag)
class OrganizationTagAdmin(admin.ModelAdmin):
    pass


tagulous.admin.register(Organization, OrganizationAdmin)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "is_staff", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "password", "full_name")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions", "clearance_level")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "is_staff")}),)
    search_fields = ("email",)
    ordering = ("email",)


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "token_key", "created", "expiry")
    fields = ("user", "name", "expiry")

    def save_model(self, request, obj, form, change):
        if not change:
            token = obj.generate_new_token()

        super().save_model(request, obj, form, change)

        if not change:
            self.message_user(request, f"The new token is: {token}")
