from django.urls import path

from account import views

urlpatterns = [
    path("<organization_code>/account/", views.AccountView.as_view(), name="account_detail"),
    path("login/", views.LoginRockyView.as_view(), name="login"),  # Bypass the two_factor login
    path("logout/", views.LogoutRockyView.as_view(), name="logout"),
    path(
        "two_factor/setup/", views.SetupRockyView.as_view(), name="setup"
    ),  # Bypass the two_factor setup show that users have to be verified
    path("recover-email/", views.RecoverEmailView.as_view(), name="recover_email"),
    path("password_reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("reset/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
