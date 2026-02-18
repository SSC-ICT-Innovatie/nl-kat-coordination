from datetime import datetime, timezone
from functools import cached_property

import structlog
import structlog.contextvars
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic.base import ContextMixin
from katalogus.client import KATalogus, get_katalogus
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from tools.models import Indemnification, Organization, OrganizationMember

from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import OOI, DeclaredScanProfile, Reference, ScanLevel
from rocky.bytes_client import BytesClient, get_bytes_client
from rocky.exceptions import (
    AcknowledgedClearanceLevelTooLowException,
    IndemnificationNotPresentException,
    TrustedClearanceLevelTooLowException,
)
from rocky.scheduler import SchedulerClient, scheduler_client

logger = structlog.get_logger(__name__)


# There are modified versions of PermLookupDict and PermWrapper from
# django.contrib.auth.context_processor.
class OrganizationPermLookupDict:
    def __init__(self, organization_member, app_label):
        self.organization_member, self.app_label = organization_member, app_label

    def __repr__(self) -> str:
        return str(self.organization_member.get_all_permissions)

    def __getitem__(self, perm_name):
        return self.organization_member.has_perm(f"{self.app_label}.{perm_name}")

    def __iter__(self):
        # To fix 'item in perms.someapp' and __getitem__ interaction we need to
        # define __iter__. See #18979 for details.
        raise TypeError("PermLookupDict is not iterable.")

    def __bool__(self):
        return False


class OrganizationPermWrapper:
    def __init__(self, organization_member):
        self.organization_member = organization_member

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self.organization_member!r})"

    def __getitem__(self, app_label):
        return OrganizationPermLookupDict(self.organization_member, app_label)

    def __iter__(self):
        # I am large, I contain multitudes.
        raise TypeError("PermWrapper is not iterable.")

    def __contains__(self, perm_name):
        """
        Lookup by "someapp" or "someapp.someperm" in perms.
        """
        if "." not in perm_name:
            # The name refers to module.
            return bool(self[perm_name])
        app_label, perm_name = perm_name.split(".", 1)
        return self[app_label][perm_name]


class OrganizationView(ContextMixin, View):
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

        organization_code = kwargs["organization_code"]
        # bind organization_code to log context
        structlog.contextvars.bind_contextvars(organization_code=organization_code)

        try:
            self.organization = Organization.objects.get(code=organization_code)
        except Organization.DoesNotExist:
            raise Http404()

        self.indemnification_present = Indemnification.objects.filter(organization=self.organization).exists()

        try:
            self.organization_member = OrganizationMember.objects.get(
                user=self.request.user, organization=self.organization
            )
        except OrganizationMember.DoesNotExist:
            if self.request.user.is_superuser:
                clearance_level = 4
            elif self.request.user.has_perm("tools.can_access_all_organizations"):
                clearance_level = -1
            else:
                raise Http404()

            # Only the Python object is created, it is not saved to the database.
            self.organization_member = OrganizationMember(
                user=self.request.user,
                organization=self.organization,
                status=OrganizationMember.STATUSES.ACTIVE,
                trusted_clearance_level=clearance_level,
                acknowledged_clearance_level=clearance_level,
            )

        if self.organization_member.blocked:
            raise PermissionDenied()

        self.octopoes_api_connector = OctopoesAPIConnector(
            settings.OCTOPOES_API, organization_code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
        )
        self.bytes_client = get_bytes_client(organization_code)

    def get_katalogus(self) -> KATalogus:
        return get_katalogus(self.organization_member)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization"] = self.organization
        context["organization_member"] = self.organization_member
        context["may_update_clearance_level"] = self.may_update_clearance_level
        context["indemnification_present"] = self.indemnification_present
        context["perms"] = OrganizationPermWrapper(self.organization_member)
        return context

    def indemnification_error(self):
        return messages.error(self.request, f"Indemnification not present at organization {self.organization}.")

    @property
    def may_update_clearance_level(self) -> bool:
        if not self.indemnification_present:
            return False

        return self.organization_member.has_clearance_level(0)

    def verify_raise_clearance_level(self, level: int) -> bool:
        if not self.indemnification_present:
            raise IndemnificationNotPresentException()

        if self.organization_member.has_clearance_level(level):
            return True
        else:
            if self.organization_member.trusted_clearance_level < level:
                raise TrustedClearanceLevelTooLowException()
            else:
                raise AcknowledgedClearanceLevelTooLowException()

    def raise_clearance_level(self, ooi_reference: Reference, level: int) -> bool:
        self.verify_raise_clearance_level(level)
        self.octopoes_api_connector.save_scan_profile(
            DeclaredScanProfile(reference=ooi_reference, level=ScanLevel(level), user_id=self.request.user.id),
            datetime.now(timezone.utc),
        )
        logger.info("Declared scan profile created", event_code="800010", ooi=ooi_reference, level=level)

        return True

    def raise_clearance_levels(self, ooi_references: list[Reference], level: int) -> bool:
        self.verify_raise_clearance_level(level)
        self.octopoes_api_connector.save_many_scan_profiles(
            [
                DeclaredScanProfile(reference=reference, level=ScanLevel(level), user_id=self.request.user.id)
                for reference in ooi_references
            ],
            datetime.now(timezone.utc),
        )
        logger.info("Declared scan profiles created", event_code="800010", ooi_count=len(ooi_references), level=level)

        return True

    def can_raise_clearance_level(self, ooi: OOI, level: int) -> bool:
        try:
            self.raise_clearance_level(ooi.reference, level)
            messages.success(self.request, _("Clearance level has been set."))
            return True
        except IndemnificationNotPresentException:
            messages.error(
                self.request,
                _("Could not raise clearance level of %s to L%s. Indemnification not present at organization %s.")
                % (ooi.reference.human_readable, level, self.organization.name),
            )

        except TrustedClearanceLevelTooLowException:
            messages.error(
                self.request,
                _(
                    "Could not raise clearance level of %s to L%s. "
                    "You were trusted a clearance level of L%s. "
                    "Contact your administrator to receive a higher clearance."
                )
                % (ooi.reference.human_readable, level, self.organization_member.max_clearance_level),
            )
        except AcknowledgedClearanceLevelTooLowException:
            messages.error(
                self.request,
                _(
                    "Could not raise clearance level of %s to L%s. "
                    "You acknowledged a clearance level of L%s. "
                    "Please accept the clearance level first on your profile page to proceed."
                )
                % (ooi.reference.human_readable, level, self.organization_member.acknowledged_clearance_level),
            )
        return False


class OrganizationPermissionRequiredMixin(PermissionRequiredMixin):
    """
    This mixin will check the permission based on OrganizationMember instead of User.
    """

    def has_permission(self) -> bool:
        perms = self.get_permission_required()
        return self.organization_member.has_perms(perms)


class OrganizationAPIMixin:
    request: Request

    def get_organization(self, field: str, value: str) -> Organization:
        lookup_param = {field: value}
        try:
            organization = Organization.objects.get(**lookup_param)
        except Organization.DoesNotExist as e:
            raise Http404(f"Organization with {field} {value} does not exist") from e

        if self.request.user.has_perm("tools.can_access_all_organizations"):
            return organization

        try:
            organization_member = OrganizationMember.objects.get(user=self.request.user, organization=organization)
        except OrganizationMember.DoesNotExist as e:
            raise Http404(f"Organization with {field} {value} does not exist") from e

        if organization_member.blocked:
            raise PermissionDenied()

        return organization

    @cached_property
    def organization(self) -> Organization:
        try:
            organization_id = self.request.query_params["organization_id"]
        except KeyError:
            pass
        else:
            return self.get_organization("id", organization_id)

        try:
            organization_code = self.request.query_params["organization_code"]
        except KeyError as e:
            raise ValidationError("Missing organization_id or organization_code query parameter") from e
        else:
            return self.get_organization("code", organization_code)

    @cached_property
    def octopoes_api_connector(self) -> OctopoesAPIConnector:
        return OctopoesAPIConnector(
            settings.OCTOPOES_API, self.organization.code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
        )

    @cached_property
    def bytes_client(self) -> BytesClient:
        return get_bytes_client(self.organization.code)

    @cached_property
    def scheduler_client(self) -> SchedulerClient:
        return scheduler_client(self.organization.code)

    @cached_property
    def valid_time(self) -> datetime:
        try:
            valid_time = self.request.query_params["valid_time"]
        except KeyError:
            return datetime.now(timezone.utc)
        else:
            try:
                ret = datetime.fromisoformat(valid_time)
            except ValueError:
                raise ValidationError(f"Wrong format for valid_time: {valid_time}")

            if not ret.tzinfo:
                ret = ret.replace(tzinfo=timezone.utc)

            return ret
