from django.urls import path

from onboarding import views

urlpatterns = [
    path(  # Step 1
        "step/introduction/registration/",
        views.OnboardingIntroductionRegistrationView.as_view(),
        name="step_1_introduction_registration",
    ),
    path(  # Step 2
        "step/organization-setup/", views.OnboardingOrganizationSetupView.as_view(), name="step_2a_organization_setup"
    ),
    path(  # Step 2 update
        "<organization_code>/step/organization-setup/update/",
        views.OnboardingOrganizationUpdateView.as_view(),
        name="step_2b_organization_update",
    ),
    path(  # Step 3
        "<organization_code>/step/indemnification-setup/",
        views.OnboardingIndemnificationSetupView.as_view(),
        name="step_3_indemnification_setup",
    ),
    path(  # Step 1 for admins: introduction
        "<organization_code>/step/introduction/",
        views.OnboardingIntroductionView.as_view(),
        name="step_1a_introduction",
    ),
    path(  # Step 4
        "<organization_code>/step/acknowledge-clearance-level/",
        views.OnboardingAcknowledgeClearanceLevelView.as_view(),
        name="step_4_trusted_acknowledge_clearance_level",
    ),
    path(  # Step 5
        "<organization_code>/step/add-scan-ooi/<ooi_type>/",
        views.OnboardingSetupScanOOIAddView.as_view(),
        name="step_5_add_scan_ooi",
    ),
    path(  # Step 6
        "<organization_code>/step/set-clearance-level/",
        views.OnboardingSetClearanceLevelView.as_view(),
        name="step_6_set_clearance_level",
    ),
    path(  # Step 7
        "<organization_code>/step/clearance-level-introduction/",
        views.OnboardingClearanceLevelIntroductionView.as_view(),
        name="step_7_clearance_level_introduction",
    ),
    path(  # Step 8
        "<organization_code>/step/setup-scan/select-plugins/",
        views.OnboardingSetupScanSelectPluginsView.as_view(),
        name="step_8_setup_scan_select_plugins",
    ),
    path(  # Step 9
        "<organization_code>/step/choose-report-type/",
        views.OnboardingChooseReportTypeView.as_view(),
        name="step_9_choose_report_type",
    ),
    path(  # Step 9a
        "<organization_code>/step/setup-scan/ooi/detail/",
        views.OnboardingCreateReportRecipe.as_view(),
        name="step_9a_setup_scan_ooi_detail",
    ),
    path(  # Step 10
        "<organization_code>/step/report/", views.OnboardingReportView.as_view(), name="step_10_report"
    ),
    path(
        "<organization_code>/step/complete-onboarding/", views.CompleteOnboarding.as_view(), name="complete_onboarding"
    ),
]
