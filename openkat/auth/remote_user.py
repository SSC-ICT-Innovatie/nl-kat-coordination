import structlog
from django.conf import settings
from django.contrib.auth.backends import RemoteUserBackend as BaseRemoteUserBackend
from django.contrib.auth.models import Group

from openkat.models import Organization, OrganizationMember

logger = structlog.get_logger(__name__)


class RemoteUserBackend(BaseRemoteUserBackend):
    """Custom RemoteUserBackend that adds users to default organizations and groups."""

    def configure_user(self, request, user, created=True):
        if settings.REMOTE_USER_DEFAULT_ORGANIZATIONS:
            try:
                user_orgs = [m.organization.code for m in user.organization_members if not m.blocked]
                for item in settings.REMOTE_USER_DEFAULT_ORGANIZATIONS:
                    organization_code, group_name = item.split(":")
                    if organization_code not in user_orgs:
                        logger.info("Adding user '%s' to organization '%s'", user, organization_code)
                        organization = Organization.objects.get(code=organization_code)
                        member = OrganizationMember.objects.create(
                            user=user,
                            organization=organization,
                            blocked=False,
                            trusted_clearance_level=4,
                            acknowledged_clearance_level=0,
                        )
                        member.groups.set([Group.objects.get(name=group_name)])
            except Exception:
                logger.exception("An error occurred while configuring user '%s'", user)
        return user
