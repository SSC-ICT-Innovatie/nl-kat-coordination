from datetime import UTC, datetime
from functools import cached_property

import structlog.contextvars
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest
from django.views import View
from django.views.generic.base import ContextMixin
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from openkat.exceptions import AcknowledgedClearanceLevelTooLowException, TrustedClearanceLevelTooLowException
from openkat.models import Organization, OrganizationMember, User


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

        organization_id = kwargs["organization_id"]
        # bind organization_ids to log context
        structlog.contextvars.bind_contextvars(organization_id=organization_id)

        try:
            self.organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise Http404()

        try:
            self.organization_member = OrganizationMember.objects.get(
                user=self.request.user, organization=self.organization
            )
        except OrganizationMember.DoesNotExist:
            if self.request.user.is_superuser:
                clearance_level = 4
            elif self.request.user.has_perm("openkat.can_access_all_organizations"):
                clearance_level = -1
            else:
                raise Http404()

            # Only the Python object is created, it is not saved to the database.
            self.organization_member = OrganizationMember(
                user=self.request.user,
                organization=self.organization,
                trusted_clearance_level=clearance_level,
                acknowledged_clearance_level=clearance_level,
            )

        if self.organization_member.blocked:
            raise PermissionDenied()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization"] = self.organization
        context["organization_member"] = self.organization_member
        context["perms"] = OrganizationPermWrapper(self.organization_member)
        return context

    def verify_raise_clearance_level(self, level: int) -> bool:
        if self.organization_member.has_clearance_level(level):
            return True
        else:
            if self.organization_member.trusted_clearance_level < level:
                raise TrustedClearanceLevelTooLowException()
            else:
                raise AcknowledgedClearanceLevelTooLowException()


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

        if self.request.user.has_perm("openkat.can_access_all_organizations"):
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
        except KeyError as e:
            raise ValidationError("Missing organization_id query parameter") from e
        else:
            return self.get_organization("id", organization_id)

    @cached_property
    def valid_time(self) -> datetime:
        try:
            valid_time = self.request.query_params["valid_time"]
        except KeyError:
            return datetime.now(UTC)
        else:
            try:
                ret = datetime.fromisoformat(valid_time)
            except ValueError:
                raise ValidationError(f"Wrong format for valid_time: {valid_time}")

            if not ret.tzinfo:
                ret = ret.replace(tzinfo=UTC)

            return ret


def filter_queryset_orgs_for_user(queryset: QuerySet, user: User, selected_organizations: set[int]) -> QuerySet:
    can_access_all_orgs_and_unassigned_objs = not selected_organizations and user.can_access_all_organizations

    if not selected_organizations and can_access_all_orgs_and_unassigned_objs:
        # If we may see all organizations and did not filter on any, we do not have to change the original queryset
        return queryset

    allowed_organizations = {org.id for org in user.organizations}

    if selected_organizations:
        organization_ids = allowed_organizations & selected_organizations

        # If the user selected organizations they don't have access to, raise PermissionDenied
        if organization_ids != selected_organizations:
            raise PermissionDenied
    else:
        organization_ids = allowed_organizations

    organizations = Organization.objects.filter(id__in=organization_ids)

    if organizations.exists():
        org_pks = [org.pk for org in organizations]

        can_access_all_orgs_and_unassigned_objs = not selected_organizations and user.can_access_all_organizations
        if hasattr(queryset.model, "organization"):
            q = Q(organization__in=organizations)
            if can_access_all_orgs_and_unassigned_objs:
                q |= Q(organization__isnull=True)
            queryset = queryset.filter(q)
        elif hasattr(queryset.model, "organizations"):
            q = Q(organizations__pk__in=org_pks)
            if can_access_all_orgs_and_unassigned_objs:
                q |= Q(organizations__isnull=True)
            queryset = queryset.filter(q).distinct()
        elif hasattr(queryset.model, "organization_id"):
            q = Q(organization_id__in=org_pks)
            if can_access_all_orgs_and_unassigned_objs:
                q |= Q(organization_id__isnull=True)
            queryset = queryset.filter(q)
    else:
        queryset = queryset.none()

    return queryset


class OrganizationFilterMixin:
    """
    Mixin to filter querysets by organization based on query parameter.

    Usage: Add ?organization=<org_id> or ?organization=<id1>&organization=<id2>
    to filter objects by one or multiple organizations. Works with both ListView and DetailView.
    """

    request: HttpRequest

    def get_queryset(self):
        return filter_queryset_orgs_for_user(
            super().get_queryset(),  # type: ignore[misc]
            self.request.user,
            {int(org_id) for org_id in self.request.GET.getlist("organization")},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        organization_ids = [int(org_id) for org_id in self.request.GET.getlist("organization")]

        if organization_ids:
            filtered_organizations = list(Organization.objects.filter(id__in=organization_ids))
            context["filtered_organizations"] = filtered_organizations
            context["filtered_organization_ids"] = organization_ids

            if len(filtered_organizations) == 1:
                context["organization"] = filtered_organizations[0]

        # Always build query string without organization params for URL building in template
        query_params = self.request.GET.copy()
        query_params.pop("organization", None)
        context["query_string_without_organization"] = query_params.urlencode()

        # Always provide filtered_organization_ids (empty list if none) for template
        if "filtered_organization_ids" not in context:
            context["filtered_organization_ids"] = []

        return context
