from typing import Any

from django.conf import settings

from openkat.models import User
from openkat.version import __version__


def feature_flags(request):
    context = {}
    for name in dir(settings):
        if name.startswith("FEATURE_"):
            context[name] = getattr(settings, name)
    return context


def languages(request):
    context = {"languages": [code for code, _ in settings.LANGUAGES]}
    return context


def organizations_including_blocked(request):
    context: dict[str, Any] = {}
    if isinstance(request.user, User):
        context["organizations_including_blocked"] = request.user.organizations_including_blocked

        # Provide organization filter query string for navigation links
        organization_ids = request.GET.getlist("organization")
        if organization_ids:
            # Build query string with organization parameters
            org_params = "&".join([f"organization={org_id}" for org_id in organization_ids])
            context["organization_query_string"] = org_params
        else:
            context["organization_query_string"] = ""

    return context


def openkat_version(request):
    context = {"openkat_version": __version__}
    return context
