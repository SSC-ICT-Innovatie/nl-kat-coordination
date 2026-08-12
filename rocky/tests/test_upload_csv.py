from io import BytesIO

import pytest
from pytest_django.asserts import assertContains

from rocky.views.upload_csv import UploadCSV
from tests.conftest import setup_request

CSV_EXAMPLES = [
    # hostname
    b"name,network\nexample.com,internet",
    # hostname without network
    b"name\nexample.net",
    # ipv4s
    b"""address,network
1.1.1.1,internet
2.2.2.2,internet
3.3.3.3,darknet""",
    # ipv6s
    b"""address,network
FE80:CD00:0000:0CDE:1257:0000:211E:729C,internet
FE80:CD00:0000:0CDE:1257:0000:211E:729D,darknet""",
    # urls
    b"""network,raw
internet,https://example.com/
darknet,https://openkat.nl/""",
    # url without network
    b"raw\nhttps://example.com/",
    b"""raw, clearance
https://potato0.com/,0
https://potato1.com/,1
https://potato2.com/,2
https://potato3.com/,3
https://potato4.com/,4
https://potato5.com/,5
https://potato.com/,potato""",
]
INPUT_TYPES = ["Hostname", "Hostname", "IPAddressV4", "IPAddressV6", "URL", "URL", "URL"]
EXPECTED_OOI_COUNTS = [2, 2, 6, 4, 4, 2, 14]


def test_upload_csv_page(rf, redteam_member):
    request = setup_request(rf.get("upload_csv"), redteam_member.user)

    response = UploadCSV.as_view()(request, organization_code=redteam_member.organization.code)
    assert response.status_code == 200
    assertContains(response, "Upload CSV")


def test_upload_csv_simple(rf, redteam_member):
    request = setup_request(rf.get("upload_csv"), redteam_member.user)
    response = UploadCSV.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200


def test_upload_bad_input(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    data = b"invalid|'\n4\bcsv|format"
    example_file = BytesIO(data)
    example_file.name = "networks.csv"

    request = setup_request(
        rf.post("upload_csv", {"object_type": "Hostname", "csv_file": example_file}), redteam_member.user
    )
    response = UploadCSV.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    task_id = mock_bytes_client().add_manual_proof.call_args[0][0]
    mock_bytes_client().add_manual_proof.assert_called_once_with(task_id, data, manual_mime_types={"manual/csv"})

    messages = list(request._messages)
    assert "could not be created for row number" in messages[0].message


def test_upload_bad_name(rf, redteam_member, mock_bytes_client):
    example_file = BytesIO(b"name,network\n\xa0\xa1,internet")
    example_file.name = "networks.cvs"

    request = setup_request(
        rf.post("upload_csv", {"object_type": "Hostname", "csv_file": example_file}), redteam_member.user
    )
    response = UploadCSV.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assert mock_bytes_client().add_manual_proof.call_count == 0
    assertContains(response, "Only CSV file supported")


def test_upload_bad_decoding(rf, redteam_member, mock_bytes_client):
    example_file = BytesIO(b"name,network\n\xa0\xa1,internet")
    example_file.name = "networks.csv"

    request = setup_request(
        rf.post("upload_csv", {"object_type": "Hostname", "csv_file": example_file}), redteam_member.user
    )
    response = UploadCSV.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assert mock_bytes_client().add_manual_proof.call_count == 0
    assertContains(response, "File could not be decoded")


@pytest.mark.parametrize(
    "example_input, input_type, expected_ooi_counts", zip(CSV_EXAMPLES, INPUT_TYPES, EXPECTED_OOI_COUNTS)
)
def test_upload_csv(
    rf,
    redteam_member,
    mock_organization_view_octopoes,
    mock_bytes_client,
    example_input,
    input_type,
    expected_ooi_counts,
):
    example_file = BytesIO(example_input)
    example_file.name = f"{input_type}.csv"

    request = setup_request(
        rf.post("upload_csv", {"object_type": input_type, "csv_file": example_file}), redteam_member.user
    )
    response = UploadCSV.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_declaration.call_count == 0
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 1

    task_id = mock_bytes_client().add_manual_proof.call_args[0][0]
    mock_bytes_client().add_manual_proof.assert_called_once_with(
        task_id, example_input, manual_mime_types={"manual/csv"}
    )

    messages = list(request._messages)
    assert "successfully added" in messages[0].message
