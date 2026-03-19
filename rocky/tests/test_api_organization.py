from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from httpx import HTTPError
from pytest_assert_utils import assert_model_attrs
from pytest_common_subject import precondition_fixture
from pytest_drf import (
    APIViewTest,
    Returns200,
    Returns201,
    Returns204,
    Returns400,
    Returns403,
    Returns409,
    Returns500,
    UsesDeleteMethod,
    UsesDetailEndpoint,
    UsesGetMethod,
    UsesListEndpoint,
    UsesPatchMethod,
    UsesPostMethod,
    ViewSetTest,
)
from pytest_drf.util import pluralized, url_for
from pytest_lambda import lambda_fixture, static_fixture
from tools.models import Organization

pytestmark = pytest.mark.django_db


def express_organization(organization: Organization) -> dict[str, Any]:
    return {
        "id": organization.id,
        "name": organization.name,
        "code": organization.code,
        "tags": [tag for tag in organization.tags.all()],
    }


express_organizations = pluralized(express_organization)


class TestOrganizationViewSet(ViewSetTest):
    @pytest.fixture
    def organizations(self):
        created_organizations = []
        organizations = [
            {"name": "Test Organization 1", "code": "test1", "tags": ["tag1", "tag2"]},
            {"name": "Test Organization 2", "code": "test2"},
        ]

        for org in organizations:
            with (
                patch("katalogus.client.KATalogusClient"),
                patch("rocky.signals.OctopoesAPIConnector"),
                patch("crisis_room.management.commands.dashboards.scheduler_client"),
                patch("crisis_room.management.commands.dashboards.get_bytes_client"),
            ):
                created_organizations.append(Organization.objects.create(**org))

        return created_organizations

    organization = lambda_fixture(lambda organizations: organizations[0])

    list_url = lambda_fixture(lambda: url_for("organization-list"))

    detail_url = lambda_fixture(lambda organization: url_for("organization-detail", organization.pk))

    client = lambda_fixture("drf_admin_client")

    class TestList(UsesGetMethod, UsesListEndpoint, Returns200):
        def test_it_returns_values(self, organizations, json):
            expected = express_organizations(organizations)
            actual = json
            assert actual == expected

    class TestCreate(UsesPostMethod, UsesListEndpoint, Returns201):
        data = static_fixture({"name": "Test Org 3", "code": "test3", "tags": ["tag2", "tag3"]})

        initial_ids = precondition_fixture(
            lambda mock_models_katalogus, mock_models_octopoes, organizations: set(
                Organization.objects.values_list("id", flat=True)
            ),
            async_=False,
        )

        @pytest.fixture(autouse=True)
        def mock_katalogus(self, mocker):
            mocker.patch("katalogus.client.KATalogusClient")

        @pytest.fixture(autouse=True)
        def mock_octopoes(self, mocker):
            mocker.patch("rocky.signals.OctopoesAPIConnector")

        @pytest.fixture(autouse=True)
        def mock_scheduler(self, mocker):
            mocker.patch("crisis_room.management.commands.dashboards.scheduler_client")

        @pytest.fixture(autouse=True)
        def mock_bytes(self, mocker):
            mocker.patch("crisis_room.management.commands.dashboards.get_bytes_client")

        def test_it_creates_new_organization(self, initial_ids, json):
            expected = initial_ids | {json["id"]}
            actual = set(Organization.objects.values_list("id", flat=True))
            assert actual == expected

        def test_it_sets_expected_attrs(self, data, json):
            organization = Organization.objects.get(pk=json["id"])

            expected = data
            assert_model_attrs(organization, expected)

        def test_it_returns_organization(self, json):
            organization = Organization.objects.get(pk=json["id"])

            expected = express_organization(organization)
            actual = json
            assert actual == expected

    class TestCreateKatalogusError(UsesPostMethod, UsesListEndpoint, Returns500):
        data = static_fixture({"name": "Test Org 3", "code": "test3", "tags": ["tag2", "tag3"]})

        @pytest.fixture(autouse=True)
        def mock_services(self, mocker):
            mocker.patch("katalogus.client.KATalogusClient.organization_exists", return_value=False)
            mocker.patch("katalogus.client.KATalogusClient.create_organization", side_effect=HTTPError("Test error"))
            mocker.patch("katalogus.client.KATalogusClient.health")
            mocker.patch("rocky.signals.OctopoesAPIConnector.root_health")
            mocker.patch("rocky.signals.OctopoesAPIConnector.create_node")

        def test_it_returns_error(self, json):
            expected = {
                "type": "server_error",
                "errors": [{"code": "error", "detail": "Failed creating organization in the Katalogus", "attr": None}],
            }
            assert json == expected

    class TestCreateOctopoesError(UsesPostMethod, UsesListEndpoint, Returns500):
        data = static_fixture({"name": "Test Org 3", "code": "test3", "tags": ["tag2", "tag3"]})

        @pytest.fixture(autouse=True)
        def mock_services(self, mocker):
            mocker.patch("katalogus.client.KATalogusClient.health")
            mocker.patch("katalogus.client.KATalogusClient.organization_exists", return_value=False)
            mocker.patch("katalogus.client.KATalogusClient.create_organization")
            mocker.patch("katalogus.client.KATalogusClient.delete_organization")  # Needed because of the "rollback"
            mocker.patch("rocky.signals.OctopoesAPIConnector.root_health")
            mocker.patch("rocky.signals.OctopoesAPIConnector.create_node", side_effect=HTTPError("Test error"))

        def test_it_returns_error(self, json):
            expected = {
                "type": "server_error",
                "errors": [{"code": "error", "detail": "Failed creating organization in Octopoes", "attr": None}],
            }
            assert json == expected

    class TestRetrieve(UsesGetMethod, UsesDetailEndpoint, Returns200):
        def test_it_returns_organization(self, organization, json):
            expected = express_organization(organization)
            actual = json
            assert actual == expected

    class TestUpdate(UsesPatchMethod, UsesDetailEndpoint, Returns200):
        data = static_fixture({"name": "Changed Organization", "code": "test4", "tags": ["tag3", "tag4"]})

        # Code is read only so shouldn't change
        expected_data = {"name": "Changed Organization", "code": "test1"}

        @pytest.fixture(autouse=True)
        def mock_services(self, mocker):
            mocker.patch("katalogus.client.KATalogusClient.health")
            mocker.patch("katalogus.client.KATalogusClient.organization_exists", return_value=False)
            mocker.patch("katalogus.client.KATalogusClient.create_organization")
            mocker.patch("katalogus.client.KATalogusClient.delete_organization")  # Needed because of the "rollback"
            mocker.patch("rocky.signals.OctopoesAPIConnector")

        def test_it_sets_expected_attrs(self, organization):
            # We must tell Django to grab fresh data from the database, or we'll
            # see our stale initial data and think our endpoint is broken!
            organization.refresh_from_db()

            assert_model_attrs(organization, self.expected_data)
            assert {str(tag) for tag in organization.tags.all()} == {"tag3", "tag4"}

        def test_it_returns_organization(self, organization, json):
            organization.refresh_from_db()

            expected = express_organization(organization)
            actual = json
            assert actual == expected

    class TestDestroy(UsesDeleteMethod, UsesDetailEndpoint, Returns204):
        initial_ids = precondition_fixture(
            lambda mock_models_katalogus, mock_models_octopoes, organizations: set(
                Organization.objects.values_list("id", flat=True)
            ),
            async_=False,
        )

        @pytest.fixture(autouse=True)
        def mock_katalogus(self, mocker):
            mocker.patch("katalogus.client.KATalogusClient")

        def test_it_deletes_organization(self, initial_ids, organization, log_output):
            expected = initial_ids - {organization.id}
            actual = set(Organization.objects.values_list("id", flat=True))
            assert actual == expected

            organization_created_log = log_output.entries[-2]
            assert organization_created_log["event"] == "%s %s deleted"
            assert organization_created_log["object"] == "Test Organization 1"
            assert organization_created_log["object_type"] == "Organization"

    class TestDestroyKatalogusError(UsesDeleteMethod, UsesDetailEndpoint, Returns500):
        @pytest.fixture(autouse=True)
        def mock_services(self, mocker):
            mocker.patch("katalogus.client.KATalogusClient.health")
            mocker.patch("katalogus.client.KATalogusClient.delete_organization", side_effect=HTTPError("Test error"))
            mocker.patch("rocky.signals.OctopoesAPIConnector")

        def test_it_returns_error(self, json):
            expected = {
                "type": "server_error",
                "errors": [{"code": "error", "detail": "Failed deleting organization in the Katalogus", "attr": None}],
            }
            assert json == expected

    class TestDestroyOctopoesError(UsesDeleteMethod, UsesDetailEndpoint, Returns500):
        @pytest.fixture(autouse=True)
        def mock_services(self, mocker):
            mocker.patch("katalogus.client.KATalogusClient")
            mocker.patch("rocky.signals.OctopoesAPIConnector.root_health")
            mocker.patch("rocky.signals.OctopoesAPIConnector.delete_node", side_effect=HTTPError("Test error"))

        def test_it_returns_error(self, json):
            expected = {
                "type": "server_error",
                "errors": [{"code": "error", "detail": "Failed deleting organization in Octopoes", "attr": None}],
            }
            assert json == expected

    class TestListNoPermission(UsesGetMethod, UsesListEndpoint, Returns403):
        client = lambda_fixture("drf_redteam_client")

    class TestCreateNoPermission(UsesPostMethod, UsesListEndpoint, Returns403):
        client = lambda_fixture("drf_redteam_client")

    class TestRetrieveNoPermission(UsesGetMethod, UsesDetailEndpoint, Returns403):
        client = lambda_fixture("drf_redteam_client")

    class TestDestroyNoPermission(UsesDeleteMethod, UsesDetailEndpoint, Returns403):
        client = lambda_fixture("drf_redteam_client")


class TestGetIndemnification(APIViewTest, UsesGetMethod, Returns200):
    # The superuser_member fixture creates the indemnification
    url = lambda_fixture(
        lambda organization, superuser_member: reverse("organization-indemnification", args=[organization.pk])
    )
    client = lambda_fixture("drf_admin_client")

    def test_it_returns_indemnification(self, json, superuser_member):
        expected = {"indemnification": True, "user": superuser_member.user.id}
        assert json == expected


class TestIndemnificationDoesNotExist(APIViewTest, UsesGetMethod, Returns200):
    url = lambda_fixture(lambda organization: reverse("organization-indemnification", args=[organization.pk]))
    client = lambda_fixture("drf_admin_client")

    def test_it_returns_no_indemnification(self, json):
        expected = {"indemnification": False, "user": None}
        assert json == expected


class TestGetIndemnificationNoPermission(APIViewTest, UsesGetMethod, Returns403):
    url = lambda_fixture(lambda organization: reverse("organization-indemnification", args=[organization.pk]))
    client = lambda_fixture("drf_redteam_client")


class TestSetIndemnification(APIViewTest, UsesPostMethod, Returns201):
    url = lambda_fixture(lambda organization: reverse("organization-indemnification", args=[organization.pk]))

    @pytest.fixture
    def client(self, drf_redteam_client, redteamuser):
        redteamuser.user_permissions.set([Permission.objects.get(codename="add_indemnification")])
        return drf_redteam_client

    def test_it_sets_indemnification(self, json, redteamuser):
        expected = {"indemnification": True, "user": redteamuser.id}
        assert json == expected


class TestSetIndemnificationNoPermission(APIViewTest, UsesPostMethod, Returns403):
    url = lambda_fixture(lambda organization: reverse("organization-indemnification", args=[organization.pk]))
    client = lambda_fixture("drf_redteam_client")


class TestIndemnificationAlreadyExists(APIViewTest, UsesPostMethod, Returns409):
    # The superuser_member fixture creates the indemnification
    url = lambda_fixture(
        lambda organization, superuser_member: reverse("organization-indemnification", args=[organization.pk])
    )
    client = lambda_fixture("drf_admin_client")

    def test_it_returns_indemnification(self, json, superuser_member):
        expected = {"indemnification": True, "user": superuser_member.user.id}
        assert json == expected


class TestRecalculateBits(APIViewTest, UsesPostMethod, Returns200):
    url = lambda_fixture(lambda organization: reverse("organization-recalculate-bits", args=[organization.pk]))

    @pytest.fixture
    def client(self, drf_redteam_client, redteamuser):
        redteamuser.user_permissions.set([Permission.objects.get(codename="can_recalculate_bits")])
        return drf_redteam_client

    @pytest.fixture(autouse=True)
    def mock_octopoes(self, mocker):
        return mocker.patch("tools.viewsets.OctopoesAPIConnector.recalculate_bits", return_value=42)

    def test_it_recalculates_bits(self, json):
        expected = {"number_of_bits": 42}
        assert json == expected


class TestRecalculateBitsNoPermission(APIViewTest, UsesPostMethod, Returns403):
    url = lambda_fixture(lambda organization: reverse("organization-recalculate-bits", args=[organization.pk]))
    client = lambda_fixture("drf_redteam_client")


class TestKatalogusCloneSettings(APIViewTest, UsesPostMethod, Returns200):
    url = lambda_fixture(lambda organization: reverse("organization-clone-katalogus-settings", args=[organization.pk]))
    data = lambda_fixture(lambda organization_b: {"to_organization": organization_b.id})

    @pytest.fixture
    def client(self, drf_redteam_client, redteamuser):
        redteamuser.user_permissions.set(
            [
                Permission.objects.get(codename="can_set_katalogus_settings"),
                Permission.objects.get(codename="can_access_all_organizations"),
            ]
        )

        return drf_redteam_client

    @pytest.fixture(autouse=True)
    def mock_katalogus(self, mocker):
        return mocker.patch("katalogus.client.KATalogusClient")

    def test_it_clones_settings(self, mock_katalogus, organization, organization_b):
        mock_katalogus().clone_all_configuration_to_organization.assert_called_once_with(
            organization.code, organization_b.code
        )


class TestCloneKatalogusSettingsNoPermission(APIViewTest, UsesPostMethod, Returns403):
    url = lambda_fixture(lambda organization: reverse("organization-clone-katalogus-settings", args=[organization.pk]))
    client = lambda_fixture("drf_redteam_client")


class TestCloneKatalogusSettingsInvalidData(APIViewTest, UsesPostMethod, Returns400):
    url = lambda_fixture(lambda organization: reverse("organization-clone-katalogus-settings", args=[organization.pk]))
    data = lambda_fixture(lambda organization_b: {"wrong_field": organization_b.id})

    @pytest.fixture
    def client(self, drf_redteam_client, redteamuser):
        redteamuser.user_permissions.set([Permission.objects.get(codename="can_set_katalogus_settings")])
        return drf_redteam_client
