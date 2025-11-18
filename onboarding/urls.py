from django.urls import path

from onboarding import views

urlpatterns = [
    path("<organization_code>/", views.OnboardingStart.as_view(), name="onboarding_index"),
    path(
        "<organization_code>/step/introduction/", views.OnboardingIntroductionView.as_view(), name="step_introduction"
    ),
    path(
        "<organization_code>/step/choose-report-info/",
        views.OnboardingChooseReportInfoView.as_view(),
        name="step_choose_report_info",
    ),
    path(
        "<organization_code>/step/clearance-level-introduction/",
        views.OnboardingClearanceLevelIntroductionView.as_view(),
        name="step_clearance_level_introduction",
    ),
    path(
        "<organization_code>/step/acknowledge-clearance-level/",
        views.OnboardingAcknowledgeClearanceLevelView.as_view(),
        name="step_acknowledge_clearance_level",
    ),
    path(
        "step/introduction/registration/",
        views.OnboardingIntroductionRegistrationView.as_view(),
        name="step_introduction_registration",
    ),
    path("step/organization-setup/", views.OnboardingOrganizationSetupView.as_view(), name="step_organization_setup"),
    path(
        "<organization_code>/step/organization-setup/update/",
        views.OnboardingOrganizationUpdateView.as_view(),
        name="step_organization_update",
    ),
    path(
        "<organization_code>/step/indemnification-setup/",
        views.OnboardingIndemnificationSetupView.as_view(),
        name="step_indemnification_setup",
    ),
    path("step/choose-user-type/", views.OnboardingChooseUserTypeView.as_view(), name="step_choose_user_type"),
    path(
        "<organization_code>/step/choose-user-type/",
        views.OnboardingChooseUserTypeView.as_view(),
        name="step_choose_user_type",
    ),
    path(
        "<organization_code>/step/complete-onboarding/", views.CompleteOnboarding.as_view(), name="complete_onboarding"
    ),
    path(
        "<organization_code>/step/account-setup/introduction/",
        views.OnboardingAccountSetupIntroView.as_view(),
        name="step_account_setup_intro",
    ),
    path(
        "<organization_code>/step/account-setup/admin/",
        views.OnboardingAccountSetupAdminView.as_view(),
        name="step_account_setup_admin",
    ),
    path(
        "<organization_code>/step/account-setup/client/",
        views.OnboardingAccountSetupClientView.as_view(),
        name="step_account_setup_client",
    ),
]
