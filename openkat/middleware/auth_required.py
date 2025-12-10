from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.urls.base import reverse
from django.utils import translation


def AuthRequiredMiddleware(get_response):
    def middleware(request):
        # URLs excluded from login
        excluded = [
            "/",
            reverse("login"),
            reverse("recover_email"),
            reverse("password_reset"),
            reverse("landing_page"),
            reverse("set_language"),
        ]

        # There won't be a request.user if auth tokens are used, but REST framework will make sure that there is an
        # authenticated user without DEFAULT_PERMISSION_CLASSES setting in settings.py.
        excluded_prefix = ["/api/", f"/{translation.get_language()}/reset/"]

        if request.path in excluded or any([request.path.startswith(prefix) for prefix in excluded_prefix]):
            return get_response(request)

        # Check if the user is logged in, and if not, redirect to login page
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        # When 2fa is enabled, check if user is verified, otherwise redirect to 2fa setup page
        if settings.TWOFACTOR_ENABLED:
            two_factor_setup = reverse("setup")

            # URLs excluded from 2fa
            excluded_2fa = [two_factor_setup, reverse("two_factor:qr"), reverse("logout")]

            if request.path in excluded_2fa or request.user.is_verified():
                return get_response(request)

            # User is not verified, meaning no user.otp_device has been set on the user, that should come from the
            # session once a user logs in, but initially gets put into the session when logging in, in the
            # TwoFactorVerifyTokenForm. The login view checks if default_device(self.request.user) exists, and else
            # redirects to the setup page. Hence, redirecting to the setup page here does not make sense and can give an
            # endless loop of redirects. If the user is not verified at this stage, we should redirect to the token step
            # of the login view.
            return redirect_to_login(request.get_full_path())

        return get_response(request)

    return middleware
