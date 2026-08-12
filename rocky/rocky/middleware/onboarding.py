from django.shortcuts import redirect
from django.urls.base import reverse
from onboarding.view_helpers import ONBOARDING_PERMISSIONS
from tools.models import OrganizationMember


def OnboardingMiddleware(get_response):
    def middleware(request):
        response = get_response(request)
        if request.user.is_authenticated:
            member_onboarded = list(filter(lambda o: o.onboarded, request.user.organization_members))

            # do not redirect itself, otherwise it will endup in endless loop
            # with too many redirects
            # exclude admin urls
            if (
                not (
                    "/onboarding/" in request.path
                    or "/admin/" in request.path
                    or "/login/" in request.path
                    or "/two_factor/" in request.path
                    or "/plugins" in request.path
                    or "/i18n/" in request.path
                    or "/introduction/" in request.path
                    or "/health/" in request.path
                    or request.path.startswith("/api/")
                )
                and not member_onboarded
            ):
                # Not onboarded superusers goes to registration of the their first organization + adding members to it.
                if request.user.is_superuser:
                    return redirect(reverse("step_1_introduction_registration"))

                # Members with these permissions can run a full DNS-report onboarding.
                if (member := OrganizationMember.objects.filter(user=request.user).first()) and member.has_perms(
                    ONBOARDING_PERMISSIONS
                ):
                    return redirect(
                        reverse("step_1a_introduction", kwargs={"organization_code": member.organization.code})
                    )

        return response

    return middleware
