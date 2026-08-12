from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls.base import reverse
from django.utils import translation


def AuthRequiredMiddleware(get_response):
    def middleware(request):
        two_factor_setup_path = reverse("setup")
        # URLs excluded from login and 2fa
        excluded = [
            "/",
            reverse("login"),
            reverse("recover_email"),
            reverse("password_reset"),
            reverse("landing_page"),
            reverse("set_language"),
            reverse("privacy_statement"),
        ]
        excluded_prefix = [
            # There won't be a request.user if auth tokens are used, but
            # Django REST framework will make sure that there is an
            # authenticated user without DEFAULT_PERMISSION_CLASSES setting
            # in settings.py.
            "/api/",
            f"/{translation.get_language()}/reset/",
        ]
        # URLs only excluded from 2fa
        excluded_2fa = [two_factor_setup_path, reverse("two_factor:qr"), reverse("logout")]

        # Check if the user is logged in, and if not, redirect to login page
        if not request.user.is_authenticated and not (
            # check if path is not in excluded list
            request.path in excluded
            # check if path starts with anything in excluded_prefix
            or any([request.path.startswith(prefix) for prefix in excluded_prefix])
        ):
            return redirect_to_login(request.get_full_path())

        # When 2fa is enabled, check if user is verified, otherwise redirect to 2fa setup page
        if (
            settings.TWOFACTOR_ENABLED
            and not (
                # check if path is not in excluded list
                request.path in excluded
                or request.path in excluded_2fa
                # check if path starts with anything in excluded_prefix
                or any([request.path.startswith(prefix) for prefix in excluded_prefix])
            )
            # This check should be after excluding /api because API users won't have `is_verified`
            and not request.user.is_verified()
        ):
            return redirect(two_factor_setup_path)

        return get_response(request)

    return middleware
