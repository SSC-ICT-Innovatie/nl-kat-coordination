from io import BytesIO
from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied
from pytest_django.asserts import assertContains
from tools.models import OrganizationMember

from rocky.views.organization_member_add import DownloadMembersTemplateView, MembersUploadView
from tests.conftest import setup_request


def test_upload_members_page(rf, superuser_member):
    request = setup_request(rf.get("organization_member_upload"), superuser_member.user)

    response = MembersUploadView.as_view()(request, organization_code=superuser_member.organization.code)
    assert response.status_code == 200
    assertContains(response, "To create a custom CSV file, make sure it meets the following criteria:")
    assertContains(response, "Upload CSV file")
    assertContains(response, "email")


def test_download_template(rf, superuser_member):
    request = setup_request(rf.get("organization_member_upload"), superuser_member.user)

    response = DownloadMembersTemplateView.as_view()(request, organization_code=superuser_member.organization.code)
    assert response.status_code == 200
    assert (
        b"".join(response.streaming_content)
        == b"full_name,email,account_type,trusted_clearance_level,acknowledged_clearance_level"
    )


def test_upload_members_page_forbidden(rf, redteam_member):
    request = setup_request(rf.get("organization_member_upload"), redteam_member.user)

    with pytest.raises(PermissionDenied):
        MembersUploadView.as_view()(request, organization_code=redteam_member.organization.code)


def test_upload_members(rf, superuser_member):
    example_file = Path(__file__).parent.joinpath("stubs").joinpath("mock.csv").open()
    assert OrganizationMember.objects.filter(organization=superuser_member.organization).count() == 1

    request = setup_request(rf.post("organization_member_upload", {"csv_file": example_file}), superuser_member.user)
    response = MembersUploadView.as_view()(request, organization_code=superuser_member.organization.code)

    assert response.status_code == 302
    messages = list(request._messages)
    assert len(messages) == 4

    assert messages[0].message == "Invalid email address: 'a.dl'"
    assert messages[1].message == "Invalid data for: 'a@b.ul'"
    assert messages[2].message == "Invalid data for: 'a@b.ml'"
    assert messages[3].message == "Successfully processed users from csv."

    assert response.url == f"/en/{superuser_member.organization.code}/members"

    assert OrganizationMember.objects.filter(organization=superuser_member.organization, status="active").count() == 5
    assert not OrganizationMember.objects.filter(organization=superuser_member.organization).last().user.password


def test_upload_bad_columns(rf, superuser_member):
    example_file = BytesIO(b"name,network\nabc,internet")
    example_file.name = "bad.cvs"
    assert OrganizationMember.objects.filter(organization=superuser_member.organization).count() == 1

    request = setup_request(rf.post("organization_member_upload", {"csv_file": example_file}), superuser_member.user)
    response = MembersUploadView.as_view()(request, organization_code=superuser_member.organization.code)

    assert OrganizationMember.objects.filter(organization=superuser_member.organization).count() == 1
    assert response.status_code == 200
