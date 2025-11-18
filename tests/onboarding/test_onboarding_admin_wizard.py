import pytest
from django.core.exceptions import PermissionDenied

from onboarding.views import (
    OnboardingAccountSetupAdminView,
    OnboardingAccountSetupClientView,
    OnboardingAccountSetupIntroView,
    OnboardingIntroductionRegistrationView,
    OnboardingOrganizationSetupView,
    OnboardingOrganizationUpdateView,
)
from tests.conftest import setup_request


def test_admin_onboarding_registration(rf, superuser_member, admin_member, client_member):
    """
    This onboarding is before an organization has been created and it is only visible for superusers.
    """
    response_superuser = OnboardingIntroductionRegistrationView.as_view()(
        setup_request(rf.get("step_introduction_registration"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )

    assert response_superuser.status_code == 200

    with pytest.raises(PermissionDenied):
        OnboardingIntroductionRegistrationView.as_view()(
            setup_request(rf.get("step_introduction_registration"), admin_member.user),
            organization_code=admin_member.organization.code,
        )

    with pytest.raises(PermissionDenied):
        OnboardingIntroductionRegistrationView.as_view()(
            setup_request(rf.get("step_introduction_registration"), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_onboarding_organization_setup(rf, superuser, adminuser, clientuser):
    response_superuser = OnboardingOrganizationSetupView.as_view()(
        setup_request(rf.get("step_organization_setup"), superuser)
    )

    # Only superusers can create organizations
    assert response_superuser.status_code == 200

    with pytest.raises(PermissionDenied):
        OnboardingOrganizationSetupView.as_view()(setup_request(rf.get("step_organization_setup"), adminuser))

    with pytest.raises(PermissionDenied):
        OnboardingOrganizationSetupView.as_view()(setup_request(rf.get("step_organization_setup"), clientuser))


def test_onboarding_organization_update(rf, superuser_member, admin_member, client_member):
    response_superuser = OnboardingOrganizationUpdateView.as_view()(
        setup_request(rf.get("step_organization_update"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )
    response_admin = OnboardingOrganizationUpdateView.as_view()(
        setup_request(rf.get("step_organization_update"), admin_member.user),
        organization_code=admin_member.organization.code,
    )

    # Only superusers and admins can update/edt/change organizations
    assert response_superuser.status_code == 200
    assert response_admin.status_code == 200

    with pytest.raises(PermissionDenied):
        OnboardingOrganizationUpdateView.as_view()(
            setup_request(rf.get("step_organization_update"), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_onboarding_account_setup_intro(rf, superuser_member, admin_member, client_member):
    response_superuser = OnboardingAccountSetupIntroView.as_view()(
        setup_request(rf.get("step_account_setup_intro"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )
    response_admin = OnboardingAccountSetupIntroView.as_view()(
        setup_request(rf.get("step_account_setup_intro"), admin_member.user),
        organization_code=admin_member.organization.code,
    )

    # Only superusers and admins can see the introduction view for single account or multiple accounts creation
    assert response_superuser.status_code == 200
    assert response_admin.status_code == 200

    with pytest.raises(PermissionDenied):
        OnboardingAccountSetupIntroView.as_view()(
            setup_request(rf.get("step_account_setup_intro"), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_onboarding_create_admin_member(rf, superuser_member, admin_member, client_member):
    response_superuser = OnboardingAccountSetupAdminView.as_view()(
        setup_request(rf.get("step_account_setup_admin"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )
    response_admin = OnboardingAccountSetupAdminView.as_view()(
        setup_request(rf.get("step_account_setup_admin"), admin_member.user),
        organization_code=admin_member.organization.code,
    )

    # Only superusers and admins can create admins
    assert response_superuser.status_code == 200
    assert response_admin.status_code == 200

    with pytest.raises(PermissionDenied):
        OnboardingAccountSetupAdminView.as_view()(
            setup_request(rf.get("step_account_setup_admin"), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_onboarding_create_client_member(rf, superuser_member, admin_member, client_member):
    response_superuser = OnboardingAccountSetupClientView.as_view()(
        setup_request(rf.get("step_account_setup_client"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )
    response_admin = OnboardingAccountSetupClientView.as_view()(
        setup_request(rf.get("step_account_setup_client"), admin_member.user),
        organization_code=admin_member.organization.code,
    )

    # Only superusers and admins can create clients
    assert response_superuser.status_code == 200
    assert response_admin.status_code == 200

    with pytest.raises(PermissionDenied):
        OnboardingAccountSetupClientView.as_view()(
            setup_request(rf.get("step_account_setup_client"), client_member.user),
            organization_code=client_member.organization.code,
        )
