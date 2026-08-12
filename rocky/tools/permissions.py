from rest_framework.permissions import BasePermission


# This is a bit clunky, but DRF doesn't allow you to specify a permission
# directly, only a Permission class
class CanRecalculateBits(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.has_perm("tools.can_recalculate_bits")


class CanSetKatalogusSettings(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.has_perm("tools.can_set_katalogus_settings")
