from datetime import datetime, timezone
from io import BytesIO

from pytest_django.asserts import assertContains

from rocky.views.upload_raw import UploadRaw
from tests.conftest import setup_request


def test_upload_raw_page(rf, redteam_member, mock_organization_view_octopoes):
    request = setup_request(rf.get("upload_raw"), redteam_member.user)

    response = UploadRaw.as_view()(request, organization_code=redteam_member.organization.code)
    assert response.status_code == 200
    assertContains(response, "Upload raw")


def test_upload_raw_simple(rf, redteam_member, mock_organization_view_octopoes):
    request = setup_request(rf.get("upload_raw"), redteam_member.user)
    response = UploadRaw.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200


def test_upload_empty(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client, network):
    example_file = BytesIO(b"")

    request = setup_request(
        rf.post(
            "upload_raw",
            {"mime_types": "Hostname", "raw_file": example_file, "ooi_id": network, "date": datetime.now(timezone.utc)},
        ),
        redteam_member.user,
    )
    response = UploadRaw.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    mock_bytes_client().upload_raw.assert_not_called()
    assertContains(response, "Required")


def test_upload_raw(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client, network):
    example_file = BytesIO(b"abc")
    example_file.name = "test"

    date = datetime.now(timezone.utc)

    request = setup_request(
        rf.post("upload_raw", {"mime_types": "abc/def,ghi", "raw_file": example_file, "ooi_id": network, "date": date}),
        redteam_member.user,
    )
    response = UploadRaw.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    mock_bytes_client().upload_raw.assert_called_once_with(
        b"abc",
        {"abc/def", "ghi"},
        input_ooi=mock_organization_view_octopoes().get().primary_key,
        input_dict=mock_organization_view_octopoes().get().serialize(),
        valid_time=date,
    )

    messages = list(request._messages)
    assert "successfully added" in messages[0].message


def test_upload_raw_empty_mime_types(rf, redteam_member, mock_bytes_client, mock_organization_view_octopoes, network):
    example_file = BytesIO(b"abc")
    example_file.name = "test"

    date = datetime.now(timezone.utc)

    request = setup_request(
        rf.post("upload_raw", {"mime_types": "abc,,,,", "raw_file": example_file, "ooi_id": network, "date": date}),
        redteam_member.user,
    )
    response = UploadRaw.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    mock_bytes_client().upload_raw.assert_called_once_with(
        b"abc",
        {"abc"},
        input_ooi=mock_organization_view_octopoes().get().primary_key,
        input_dict=mock_organization_view_octopoes().get().serialize(),
        valid_time=date,
    )

    messages = list(request._messages)
    assert "successfully added" in messages[0].message
