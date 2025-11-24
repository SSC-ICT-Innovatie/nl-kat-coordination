from collections.abc import Sequence

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.views import View
from django.views.generic import CreateView, DeleteView, UpdateView
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.request import Request

from objects.models import object_type_by_name


def has_token_permission(request: Request, perms: Sequence[str], action: str | None = "retrieve") -> bool:
    if not hasattr(request, "auth") or not isinstance(request.auth, dict):
        return False

    token_perms = request.auth.get("permissions", {})

    if not isinstance(token_perms, dict):
        return False

    for view_perm in perms:
        if view_perm not in token_perms:
            return False

        if not isinstance(token_perms[view_perm], dict) or token_perms[view_perm] == {}:
            continue

        if action == "retrieve" or action == "get":
            continue  # The checks below apply to the "list" action only

        if "search" in token_perms[view_perm] and request.GET.get("search") not in token_perms[view_perm]["search"]:
            return False

        if "limit" in token_perms[view_perm] and int(request.GET.get("limit")) != int(token_perms[view_perm]["limit"]):
            return False

    # The auth token has all required permissions
    return True


class KATModelPermissions(DjangoModelPermissions):
    # We change the permissions map to include the view permissions for GET/OPTIONS/HEAD.
    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_permission(self, request, view):
        """
        Generic endpoints determine the permissions from the request.data provided, so we override this method
        without a super() call because we call self.view_perms() instead of assuming we determine permissions through
        a queryset and request.method only, meaning it is a lot cleaner to extend this class in
        KATMultiModelPermissions
        """

        if has_token_permission(request, self._view_perms(request, view), view.action):
            return True

        if not request.user or (not request.user.is_authenticated and self.authenticated_users_only):
            return False

        if getattr(view, "_ignore_model_permissions", False):
            return True

        return request.user.has_perms(self._view_perms(request, view))

    def has_object_permission(self, request, view, obj):
        if self.has_token_object_permission(request, view, obj):
            return True

        return super().has_permission(request, view)

    def has_token_object_permission(self, request, view, obj):
        if not hasattr(request, "auth") or not isinstance(request.auth, dict):
            return False

        view_perms = self._view_perms(request, view)
        token_perms = request.auth.get("permissions", {})

        if not isinstance(token_perms, dict):
            return False

        for view_perm in view_perms:
            if view_perm not in token_perms:
                return False

            if not isinstance(token_perms[view_perm], dict) or token_perms[view_perm] == {}:
                continue

            if "pks" in token_perms[view_perm] and obj.pk not in token_perms[view_perm]["pks"]:
                return False

        return True

    def _view_perms(self, request: Request, view: View) -> list[str]:
        view_perms = set(view.permission_required) if hasattr(view, "permission_required") else set()

        return list(set(self.get_required_permissions(request.method, self._queryset(view).model)) | view_perms)


class KATMultiModelPermissions(KATModelPermissions):
    def _view_perms(self, request, view):
        perms: list[str] = []
        models = {key.lower(): model for key, model in object_type_by_name().items()}

        for key in request.data:
            if key in models:
                perms.extend(self.get_required_permissions(request.method, models[key]))

        return perms


class KATModelPermissionRequiredMixin(PermissionRequiredMixin):
    """DRF-like behavior for regular views, inferred not by the HTTP method but by the view type."""

    perms_map = {
        CreateView.__name__: ["%(app_label)s.add_%(model_name)s"],
        UpdateView.__name__: ["%(app_label)s.change_%(model_name)s"],
        DeleteView.__name__: ["%(app_label)s.delete_%(model_name)s"],
    }

    def get_permission_required(self) -> list[str]:
        try:
            permissions_required = list(super().get_permission_required())
        except ImproperlyConfigured:
            permissions_required = []

        if not issubclass(self.__class__, CreateView | UpdateView | DeleteView):
            return permissions_required

        kwargs = {"app_label": self.model._meta.app_label, "model_name": self.model._meta.model_name}

        if issubclass(self.__class__, CreateView):
            permissions_required.extend([perm % kwargs for perm in self.perms_map[CreateView.__name__]])

        if issubclass(self.__class__, UpdateView):
            permissions_required.extend([perm % kwargs for perm in self.perms_map[UpdateView.__name__]])

        if issubclass(self.__class__, DeleteView):
            permissions_required.extend([perm % kwargs for perm in self.perms_map[DeleteView.__name__]])

        return permissions_required
