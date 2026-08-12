from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from account.models import AuthToken

User = get_user_model()


@admin.register(User)
class KATUserAdmin(UserAdmin):
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
