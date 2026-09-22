import pytest
from django.core.exceptions import PermissionDenied
from pytest_django.asserts import assertContains, assertNotContains

from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding, RiskLevelSeverity
from octopoes.models.ooi.software import Software, SoftwareInstance
from octopoes.models.pagination import Paginated
from octopoes.models.tree import ReferenceTree
from rocky.views.finding_list import FindingListView
from rocky.views.ooi_add import OOIAddView
from rocky.views.ooi_detail import OOIDetailView
from rocky.views.ooi_findings import OOIFindingListView
from rocky.views.ooi_mute import MuteFindingsBulkView, MuteFindingView
from tests.conftest import setup_request

TREE_DATA = {
    "root": {
        "reference": "Finding|Network|testnetwork|KAT-000",
        "children": {"ooi": [{"reference": "Network|testnetwork", "children": {}}]},
    },
    "store": {
        "Network|testnetwork": {"object_type": "Network", "primary_key": "Network|testnetwork", "name": "testnetwork"},
        "Finding|Network|testnetwork|KAT-000": {
            "object_type": "Finding",
            "primary_key": "Finding|Network|testnetwork|KAT-000",
            "ooi": "Network|testnetwork",
            "finding_type": "KATFindingType|KAT-000",
        },
    },
}


MUTED_FINDING_TREE_DATA = {
    "root": {
        "reference": "MutedFinding|Network|testnetwork|KAT-000",
        "children": {"ooi": [{"reference": "Finding|Network|testnetwork|KAT-000", "children": {}}]},
    },
    "store": {
        "MutedFinding|Network|testnetwork|KAT-000": {
            "object_type": "MutedFinding",
            "primary_key": "MutedFinding|Network|testnetwork|KAT-000",
            "finding": "Finding|Network|testnetwork|KAT-000",
            "reason": "Hallo",
        },
        "Network|testnetwork": {"object_type": "Network", "primary_key": "Network|testnetwork", "name": "testnetwork"},
        "Finding|Network|testnetwork|KAT-000": {
            "object_type": "Finding",
            "primary_key": "Finding|Network|testnetwork|KAT-000",
            "ooi": "Network|testnetwork",
            "finding_type": "KATFindingType|KAT-000",
        },
    },
}


def test_ooi_finding_list(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)

    request = setup_request(rf.get("ooi_findings", {"ooi_id": "Network|testnetwork"}), client_member.user)
    response = OOIFindingListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    # The object tree itself, plus the SoftwareInstance-only tree the software traversal needs.
    assert mock_organization_view_octopoes().get_tree.call_count == 2
    assertContains(response, "Add finding")


@pytest.mark.parametrize("member", ["superuser_member", "redteam_member"])
def test_mute_finding_button_is_visible(request, member, rf, mock_organization_view_octopoes, mock_scheduler, mocker):
    mocker.patch("katalogus.client.KATalogusClient")
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)

    member = request.getfixturevalue(member)

    response = OOIDetailView.as_view()(
        setup_request(rf.get("ooi_detail", {"ooi_id": "Network|testnetwork"}), member.user),
        organization_code=member.organization.code,
    )

    assert response.status_code == 200
    assertContains(response, "Mute finding")


@pytest.mark.parametrize("member", ["admin_member", "client_member"])
def test_mute_finding_button_is_not_visible_without_perms(
    request, member, rf, mock_organization_view_octopoes, mock_scheduler, mocker
):
    mocker.patch("katalogus.client.KATalogusClient")
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)

    member = request.getfixturevalue(member)

    response = OOIDetailView.as_view()(
        setup_request(rf.get("ooi_detail", {"ooi_id": "Network|testnetwork"}), member.user),
        organization_code=member.organization.code,
    )

    assert response.status_code == 200
    assertNotContains(response, "Mute finding")


@pytest.mark.parametrize("member", ["superuser_member", "redteam_member"])
def test_mute_finding_form_view(request, member, rf, mock_organization_view_octopoes):
    member = request.getfixturevalue(member)
    response = MuteFindingView.as_view()(
        setup_request(rf.get("finding_mute", {"ooi_id": "Finding|Network|testnetwork|KAT-000"}), member.user),
        organization_code=member.organization.code,
    )

    assert response.status_code == 200

    assertContains(response, "Reason:")
    assertContains(response, "Mute")
    assertContains(response, "Cancel")
    assertContains(response, "Mute finding: ")


@pytest.mark.parametrize("member", ["admin_member", "client_member"])
def test_mute_finding_form_view_no_perms(request, member, rf, mock_organization_view_octopoes):
    member = request.getfixturevalue(member)
    with pytest.raises(PermissionDenied):
        MuteFindingView.as_view()(
            setup_request(rf.get("finding_mute", {"ooi_id": "Finding|Network|testnetwork|KAT-000"}), member.user),
            organization_code=member.organization.code,
        )


def test_mute_finding_post(
    rf,
    redteam_member,
    mock_bytes_client,
    mock_scheduler,
    mock_organization_view_octopoes,
    lazy_task_list_with_boefje,
    mocker,
):
    # post from the finding mute view
    muted_finding = MUTED_FINDING_TREE_DATA["store"]["MutedFinding|Network|testnetwork|KAT-000"]
    request = setup_request(
        rf.post(
            "finding_mute",
            {
                "ooi_type": muted_finding["object_type"],
                "finding": muted_finding["finding"],
                "reason": muted_finding["reason"],
            },
        ),
        redteam_member.user,
    )
    # Uses same ooi_add post request to add a MuteFinding object
    response = OOIAddView.as_view()(
        request, organization_code=redteam_member.organization.code, ooi_type="MutedFinding"
    )

    # Redirects to ooi_detail
    assert response.status_code == 302

    mocker.patch("katalogus.client.KATalogusClient")
    resulted_request = setup_request(rf.get(response.url), redteam_member.user)

    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(MUTED_FINDING_TREE_DATA)
    mock_scheduler.get_lazy_task_list.return_value = lazy_task_list_with_boefje

    resulted_response = OOIDetailView.as_view()(resulted_request, organization_code=redteam_member.organization.code)

    assert resulted_response.status_code == 200
    assertContains(resulted_response, "Reason")
    assertContains(resulted_response, "Muted Network|testnetwork|KAT-000")
    assertContains(resulted_response, "MutedFinding")
    assertContains(resulted_response, muted_finding["reason"])
    assertContains(resulted_response, "KAT-000 @ testnetwork")


def test_muted_finding_button_not_presence(rf, mock_organization_view_octopoes, network, finding_types, redteam_member):
    mock_organization_view_octopoes().list_findings.return_value = Paginated[Finding](
        count=1,
        items=[
            Finding(
                finding_type=finding_types[0].reference,
                ooi=network.reference,
                proof="proof",
                description="test description 123",
                reproduce="reproduce",
            )
        ],
    )
    mock_organization_view_octopoes().load_objects_bulk.return_value = {
        network.reference: network,
        finding_types[0].reference: finding_types[0],
    }

    response = FindingListView.as_view()(
        setup_request(rf.get("finding_list"), redteam_member.user), organization_code=redteam_member.organization.code
    )

    assert response.status_code == 200
    assertContains(
        response,
        '<a class="button ghost" href="#mute-findings-modal"><icon aria-hidden="true" '
        'class="icon ti-bell-off"></icon>Mute findings</a>',
    )


@pytest.mark.parametrize("member", ["superuser_member", "redteam_member"])
def test_muted_finding_button_presence_more_findings_and_post(
    rf,
    request,
    member,
    mock_organization_view_octopoes,
    network,
    finding_types,
    mocker,
    mock_bytes_client,
    mock_scheduler,
):
    member = request.getfixturevalue(member)
    finding_1 = Finding(
        finding_type=finding_types[0].reference,
        ooi=network.reference,
        proof="proof",
        description="test description 123",
        reproduce="reproduce",
    )
    finding_2 = Finding(
        finding_type=finding_types[1].reference,
        ooi=network.reference,
        proof="proof",
        description="test description 123",
        reproduce="reproduce",
    )
    mock_organization_view_octopoes().list_findings.return_value = Paginated[Finding](
        count=2, items=[finding_1, finding_2]
    )

    mock_organization_view_octopoes().load_objects_bulk.return_value = {
        network.reference: network,
        finding_types[0].reference: finding_types[0],
        finding_types[1].reference: finding_types[1],
    }

    response = FindingListView.as_view()(
        setup_request(rf.get("finding_list"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200
    assertContains(response, '<input class="toggle-all" data-toggle-target="finding" type="checkbox">', html=True)
    assertContains(response, '<input type="checkbox" name="finding" value="' + finding_1.primary_key + '">', html=True)
    assertContains(
        response,
        '<a class="button ghost" href="#mute-findings-modal"><icon aria-hidden="true" '
        'class="icon ti-bell-off"></icon>Mute findings</a>',
    )

    request = setup_request(
        rf.post("finding_mute_bulk", {"finding": [finding_1, finding_2], "reason": "testing"}), member.user
    )

    response_post = MuteFindingsBulkView.as_view()(request, organization_code=member.organization.code)

    assert response_post.status_code == 302


@pytest.mark.parametrize("member", ["admin_member", "client_member"])
def test_can_mute_findings_perms(rf, request, member, mock_organization_view_octopoes, network, finding_types):
    member = request.getfixturevalue(member)
    mock_organization_view_octopoes().list_findings.return_value = Paginated[Finding](
        count=2,
        items=[
            Finding(
                finding_type=finding_types[0].reference,
                ooi=network.reference,
                proof="proof",
                description="test description 123",
                reproduce="reproduce",
            ),
            Finding(
                finding_type=finding_types[1].reference,
                ooi=network.reference,
                proof="proof",
                description="test description 123",
                reproduce="reproduce",
            ),
        ],
    )

    mock_organization_view_octopoes().load_objects_bulk.return_value = {
        network.reference: network,
        finding_types[0].reference: finding_types[0],
        finding_types[1].reference: finding_types[1],
    }

    response = FindingListView.as_view()(
        setup_request(rf.get("finding_list"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200
    assertNotContains(
        response,
        '<a class="button ghost" href="#mute-findings-modal"><icon aria-hidden="true" '
        'class="icon ti-bell-off"></icon>Mute findings</a>',
    )


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_findings_list_filtering(
    rf,
    request,
    member,
    mock_organization_view_octopoes,
    network,
    finding_types,
    mocker,
    mock_bytes_client,
    mock_scheduler,
):
    member = request.getfixturevalue(member)
    # Severity Critical
    finding_1 = Finding(
        finding_type=finding_types[1].reference,
        ooi=network.reference,
        proof="proof",
        description="test description 123",
        reproduce="reproduce",
    )
    # Severity Low
    finding_2 = Finding(
        finding_type=finding_types[2].reference,
        ooi=network.reference,
        proof="proof",
        description="test description 123",
        reproduce="reproduce",
    )
    mock_organization_view_octopoes().list_findings.return_value = Paginated[Finding](
        count=2, items=[finding_1, finding_2]
    )

    mock_organization_view_octopoes().load_objects_bulk.return_value = {
        network.reference: network,
        finding_types[1].reference: finding_types[1],
        finding_types[2].reference: finding_types[2],
    }

    response = FindingListView.as_view()(
        setup_request(rf.get("finding_list"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200
    assert len(response.context_data["object_list"]) == 2

    request_filtering = setup_request(rf.get("finding_list", {"severity": "low"}), member.user)
    FindingListView.as_view()(request_filtering, organization_code=member.organization.code)

    assert mock_organization_view_octopoes().list_findings.mock_calls[1].kwargs["severities"] == {RiskLevelSeverity.LOW}


SOFTWARE_TREE_DATA = {
    "root": {"reference": "Hostname|internet|example.com", "children": {}},
    "store": {
        "Hostname|internet|example.com": {
            "object_type": "Hostname",
            "primary_key": "Hostname|internet|example.com",
            "name": "example.com",
            "network": "Network|internet",
        }
    },
}


def software_instance_tree(asset: str, *instances: SoftwareInstance) -> ReferenceTree:
    """The SoftwareInstance-only tree octopoes returns for the software traversal."""
    return ReferenceTree.model_validate(
        {
            "root": {"reference": asset, "children": {}},
            "store": {str(instance.reference): instance.model_dump(mode="json") for instance in instances},
        }
    )


def test_ooi_findings_include_cve_bound_to_software(rf, client_member, mock_organization_view_octopoes):
    """A CVE bound to the Software OOI must surface on the asset that runs it (#5321).

    Software is not traversable, so the object tree never reaches such a finding: it is only
    found by walking asset -> SoftwareInstance -> Software -> Finding.
    """
    software = Software(name="nginx", version="1.0")
    finding_type = CVEFindingType(
        id="CVE-2024-0001",
        description="nginx has a known vulnerability",
        risk_score=9.8,
        risk_severity=RiskLevelSeverity.CRITICAL,
    )
    finding = Finding(finding_type=finding_type.reference, ooi=software.reference, description="")

    instance = SoftwareInstance(ooi=Reference.from_str("IPPort|internet|1.1.1.1|tcp|443"), software=software.reference)
    mock_organization_view_octopoes().get_tree.side_effect = [
        ReferenceTree.model_validate(SOFTWARE_TREE_DATA),
        software_instance_tree("Hostname|internet|example.com", instance),
    ]
    mock_organization_view_octopoes().query_many.return_value = [(str(instance.reference), finding)]
    mock_organization_view_octopoes().load_objects_bulk.return_value = {finding_type.reference: finding_type}

    request = setup_request(rf.get("ooi_findings", {"ooi_id": "Hostname|internet|example.com"}), client_member.user)
    response = OOIFindingListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "CVE-2024-0001")

    # The software sits several hops away (Hostname -> ... -> IPPort -> SoftwareInstance), so the
    # traversal must ask for more than the two levels the detail page itself renders.
    software_tree_call = mock_organization_view_octopoes().get_tree.call_args_list[1]
    assert software_tree_call.kwargs["types"] == {SoftwareInstance}
    assert software_tree_call.kwargs["depth"] > 2


def test_ooi_findings_do_not_duplicate_a_finding_reached_twice(rf, client_member, mock_organization_view_octopoes):
    """One package on two ports yields the same finding twice; the page must show it once."""
    software = Software(name="nginx", version="1.0")
    finding_type = CVEFindingType(id="CVE-2024-0001", risk_score=9.8, risk_severity=RiskLevelSeverity.CRITICAL)
    finding = Finding(finding_type=finding_type.reference, ooi=software.reference, description="")

    ports = [
        SoftwareInstance(ooi=Reference.from_str(f"IPPort|internet|1.1.1.1|tcp|{port}"), software=software.reference)
        for port in (80, 443)
    ]
    mock_organization_view_octopoes().get_tree.side_effect = [
        ReferenceTree.model_validate(SOFTWARE_TREE_DATA),
        software_instance_tree("Hostname|internet|example.com", *ports),
    ]
    mock_organization_view_octopoes().query_many.return_value = [
        (str(instance.reference), finding) for instance in ports
    ]
    mock_organization_view_octopoes().load_objects_bulk.return_value = {finding_type.reference: finding_type}

    request = setup_request(rf.get("ooi_findings", {"ooi_id": "Hostname|internet|example.com"}), client_member.user)
    response = OOIFindingListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert [str(finding.reference) for finding, _finding_type in response.context_data["findings"]] == [
        str(finding.reference)
    ]


def test_ooi_findings_skip_the_traversal_without_software(rf, client_member, mock_organization_view_octopoes):
    """No SoftwareInstance in reach means nothing to query -- don't ask octopoes anyway."""
    mock_organization_view_octopoes().get_tree.side_effect = [
        ReferenceTree.model_validate(SOFTWARE_TREE_DATA),
        ReferenceTree.model_validate(
            {"root": {"reference": "Hostname|internet|example.com", "children": {}}, "store": {}}
        ),
    ]

    request = setup_request(rf.get("ooi_findings", {"ooi_id": "Hostname|internet|example.com"}), client_member.user)
    response = OOIFindingListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    mock_organization_view_octopoes().query_many.assert_not_called()
