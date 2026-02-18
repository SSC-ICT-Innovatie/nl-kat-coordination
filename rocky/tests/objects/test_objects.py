import csv
import io
import json

import pytest
from django.urls import resolve, reverse
from pytest_django.asserts import assertContains, assertNotContains
from tools.models import Indemnification

from octopoes.models import ScanLevel, ScanProfileType
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from octopoes.models.pagination import Paginated
from octopoes.models.types import OOIType
from rocky.views.ooi_list import OOIListExportView, OOIListView
from tests.conftest import setup_request


def test_ooi_list(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)
    request = rf.get(url)
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=200, items=[Network(name="testnetwork")] * 150
    )

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert mock_organization_view_octopoes().list_objects.call_count == 2
    assertContains(response, "testnetwork")


def test_ooi_list_with_clearance_type_filter_and_clearance_level_filter(
    rf, client_member, mock_organization_view_octopoes
):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)
    request = rf.get(url, {"clearance_level": [0, 1], "clearance_type": ["declared", "inherited"]})
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=200, items=[Network(name="testnetwork")] * 150
    )

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert mock_organization_view_octopoes().list_objects.call_count == 2

    list_call_0 = mock_organization_view_octopoes().list_objects.call_args_list[0]
    assert list_call_0.kwargs["limit"] == 0
    assert list_call_0.kwargs["scan_level"] == {ScanLevel.L0, ScanLevel.L1}
    assert list_call_0.kwargs["scan_profile_type"] == {ScanProfileType.DECLARED, ScanProfileType.INHERITED}

    list_call_1 = mock_organization_view_octopoes().list_objects.call_args_list[1]
    assert list_call_1.kwargs["limit"] == 150
    assert list_call_1.kwargs["offset"] == 0
    assert list_call_1.kwargs["scan_level"] == {ScanLevel.L0, ScanLevel.L1}
    assert list_call_1.kwargs["scan_profile_type"] == {ScanProfileType.DECLARED, ScanProfileType.INHERITED}

    assertContains(response, "testnetwork")
    assertContains(response, "Showing 150 of 200 objects")


def test_ooi_list_search(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)
    request = rf.get(url, {"search": "testnetwork"})
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    network = Network(name="testnetwork")

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=2, items=[network, Hostname(name="example.com", network=network.reference)]
    )

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    list_call_1 = mock_organization_view_octopoes().list_objects.call_args_list[0]
    assert list_call_1.kwargs["search_string"] == "testnetwork"

    assertContains(response, "Showing 2 of 2 objects")


def test_ooi_list_delete_multiple(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)
    client_member.trusted_clearance_level = 0
    client_member.acknowledged_clearance_level = 0
    client_member.save()

    request = rf.post(
        url,
        data={"ooi": ["Network|internet", "Hostname|internet|scanme.org"], "scan-profile": "L0", "action": "delete"},
    )
    setup_request(request, client_member.user)
    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().delete_many.call_count == 1


def test_ooi_list_delete_none(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    request = rf.post(url, data={"ooi": [], "scan-profile": "L0", "action": "delete"})
    setup_request(request, client_member.user)

    client_member.acknowledged_clearance_level = 0
    client_member.save()
    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 422


def test_ooi_list_unknown_action(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    request = rf.post(url, data={"ooi": ["Network|internet"], "scan-profile": "L0", "action": "None"})
    setup_request(request, client_member.user)

    client_member.acknowledged_clearance_level = 0
    client_member.save()
    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 404


def test_update_scan_profile_multiple(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)
    client_member.trusted_clearance_level = 1
    client_member.acknowledged_clearance_level = 1
    client_member.save()
    request = rf.post(
        url,
        data={
            "ooi": ["Network|internet", "Hostname|internet|scanme.org"],
            "clearance_type": "declared",
            "level": "1",
            "action": "update-scan-profile",
        },
    )
    setup_request(request, client_member.user)
    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_scan_profiles.call_count == 1


def test_update_scan_profile_single(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)
    client_member.trusted_clearance_level = 4
    client_member.acknowledged_clearance_level = 4
    client_member.save()

    request = rf.post(
        url,
        data={
            "ooi": ["Hostname|internet|scanme.org"],
            "clearance_type": "declared",
            "level": "4",
            "action": "update-scan-profile",
        },
    )

    setup_request(request, client_member.user)
    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_scan_profiles.call_count == 1


def test_update_scan_profile_to_inherit(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    request = rf.post(
        url,
        data={"ooi": ["Hostname|internet|scanme.org"], "clearance_type": "inherited", "action": "update-scan-profile"},
    )
    setup_request(request, client_member.user)
    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_scan_profiles.call_count == 1


def test_update_scan_profile_to_inherit_connection_error(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().save_many_scan_profiles.side_effect = ConnectionError
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    request = rf.post(
        url,
        data={"ooi": ["Hostname|internet|scanme.org"], "clearance_type": "inherited", "action": "update-scan-profile"},
    )
    setup_request(request, client_member.user)
    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 500


def test_update_scan_profile_to_inherit_object_not_found(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().save_many_scan_profiles.side_effect = ObjectNotFoundException("nothing found")
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    request = rf.post(
        url,
        data={"ooi": ["Hostname|internet|scanme.org"], "clearance_type": "inherited", "action": "update-scan-profile"},
    )
    setup_request(request, client_member.user)
    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 404


def test_update_scan_profiles_forbidden_acknowledged(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    request = rf.post(
        url,
        data={
            "ooi": ["Network|internet", "Hostname|internet|scanme.org"],
            "clearance_type": "declared",
            "level": "1",
            "action": "update-scan-profile",
        },
    )

    client_member.acknowledged_clearance_level = -1
    client_member.save()

    setup_request(request, client_member.user)

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302
    assert response.headers["location"] == "/en/test/account/"
    assert (
        list(request._messages)[0].message
        == "Could not raise clearance level to L1. You acknowledged a clearance level of L-1. "
        "Please accept the clearance level below to proceed."
    )


def test_update_scan_profiles_forbidden_trusted(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    request = rf.post(
        url,
        data={"ooi": ["Network|internet"], "clearance_type": "declared", "level": "1", "action": "update-scan-profile"},
    )

    client_member.trusted_clearance_level = -1
    client_member.save()

    setup_request(request, client_member.user)

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 403


def test_update_scan_profiles_no_indemnification(rf, redteam_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": redteam_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    request = rf.post(
        url,
        data={
            "ooi": ["Network|internet", "Hostname|internet|scanme.org"],
            "clearance_type": "declared",
            "level": "1",
            "action": "update-scan-profile",
        },
    )

    Indemnification.objects.get(user=redteam_member.user).delete()

    setup_request(request, redteam_member.user)

    response = OOIListView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 403


def test_update_scan_profiles_octopoes_down(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().save_many_scan_profiles.side_effect = ConnectionError
    client_member.trusted_clearance_level = 2
    client_member.acknowledged_clearance_level = 2
    client_member.save()
    request = rf.post(
        "ooi_list",
        data={
            "ooi": ["Network|internet", "Hostname|internet|scanme.org"],
            "clearance_type": "declared",
            "level": 2,
            "action": "update-scan-profile",
        },
    )

    setup_request(request, client_member.user)

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 500


def test_update_scan_profiles_object_not_found(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().save_many_scan_profiles.side_effect = ObjectNotFoundException("gone")
    client_member.trusted_clearance_level = 2
    client_member.acknowledged_clearance_level = 2
    client_member.save()

    request = rf.post(
        "ooi_list",
        data={
            "ooi": ["Network|internet", "Hostname|internet|scanme.org"],
            "clearance_type": "declared",
            "level": 2,
            "action": "update-scan-profile",
        },
    )

    setup_request(request, client_member.user)

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 404


def test_delete_octopoes_down(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().delete_many.side_effect = ConnectionError

    request = rf.post(
        "ooi_list",
        data={
            "ooi": ["Network|internet", "Hostname|internet|scanme.org"],
            "clearance_type": "declared",
            "level": 2,
            "action": "delete",
        },
    )
    client_member.trusted_clearance_level = 4
    client_member.acknowledged_clearance_level = 4
    client_member.save()
    setup_request(request, client_member.user)

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 500


def test_delete_object_not_found(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().delete_many.side_effect = ObjectNotFoundException("gone")

    request = rf.post(
        "ooi_list",
        data={
            "ooi": ["Network|internet", "Hostname|internet|scanme.org"],
            "clearance_type": "declared",
            "level": 2,
            "action": "delete",
        },
    )

    setup_request(request, client_member.user)

    response = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 404


def test_ooi_list_export_json(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list_export", kwargs=kwargs)
    request = rf.get(url, {"file_type": "json"})
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=200, items=[Network(name="testnetwork")] * 150
    )

    response = OOIListExportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert mock_organization_view_octopoes().list_objects.call_count == 1

    exported_objects = json.loads(response.content.decode())
    assert len(exported_objects) == 151
    assert "observed_at" in exported_objects[0]
    assert "filters" in exported_objects[0]

    assert exported_objects[1] == {"key": "Network|testnetwork", "name": "testnetwork", "ooi_type": "Network"}
    assert exported_objects[2] == {"key": "Network|testnetwork", "name": "testnetwork", "ooi_type": "Network"}


def test_ooi_list_export_csv(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list_export", kwargs=kwargs)
    request = rf.get(url, {"file_type": "csv"})
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=200, items=[Network(name="testnetwork")] * 150
    )

    response = OOIListExportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv"
    assert mock_organization_view_octopoes().list_objects.call_count == 1

    exported_objects = list(csv.DictReader(io.StringIO(response.content.decode()), delimiter=",", quotechar='"'))

    assert len(exported_objects) == 152
    assert "observed_at" in exported_objects[0]
    assert "filters" in exported_objects[0]


def test_ooi_list_filtered_export_csv(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list_export", kwargs=kwargs)
    request = rf.get(
        url, {"file_type": "csv", "ooi_type": "Network", "clearance_type": "inherited", "clearance_level": 3}
    )
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=200, items=[Network(name="testnetwork")] * 150
    )

    response = OOIListExportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv"
    assert mock_organization_view_octopoes().list_objects.call_count == 1

    mock_calls = mock_organization_view_octopoes().list_objects.mock_calls
    assert list(mock_calls[0].kwargs["scan_level"])[0].value == 3
    assert mock_calls[0].args[0].pop() == Network
    assert list(mock_calls[0].kwargs["scan_profile_type"])[0].value == "inherited"


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member"])
def test_delete_perms_object_list(request, member, rf, mock_organization_view_octopoes):
    member = request.getfixturevalue(member)
    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=200, items=[Network(name="testnetwork")] * 150
    )

    url = reverse("ooi_list", kwargs={"organization_code": member.organization.code})
    request = rf.get(url)
    request.resolver_match = resolve(url)
    response = OOIListView.as_view()(setup_request(request, member.user), organization_code=member.organization.code)

    assert response.status_code == 200

    assertContains(response, "Delete")


def test_delete_perms_object_list_clients(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=200, items=[Network(name="testnetwork")] * 150
    )

    url = reverse("ooi_list", kwargs={"organization_code": client_member.organization.code})
    request = rf.get(url)
    request.resolver_match = resolve(url)
    response = OOIListView.as_view()(
        setup_request(request, client_member.user), organization_code=client_member.organization.code
    )

    assert response.status_code == 200

    assertNotContains(response, "Delete")
