from datetime import datetime, timezone

from django.urls import resolve, reverse
from tools.urlconverters import TemporalContextConverter

from octopoes.models.ooi.network import Network
from octopoes.models.pagination import Paginated
from octopoes.models.types import OOIType
from rocky.views.mixins import ObservedAtMixin
from rocky.views.ooi_list import OOIListView
from tests.conftest import setup_request


def test_observed_at_defaults_to_now(mocker):
    """Without a temporal context (the "now" segment resolves to None), observed_at is the present."""
    mock_mixin_datetime = mocker.patch("rocky.views.mixins.datetime")
    now = datetime(2023, 10, 24, 9, 34, 56, 316699, tzinfo=timezone.utc)
    mock_mixin_datetime.now.return_value = now

    mixin = ObservedAtMixin()
    mixin.temporal_context = None

    assert mixin.observed_at == now
    assert mixin.is_historic_view is False
    assert mixin.temporal_string == "now"


def test_observed_at_uses_temporal_context():
    """A temporal context set from the URL segment drives observed_at directly."""
    moment = datetime(2023, 10, 24, 9, 34, 56, tzinfo=timezone.utc)

    mixin = ObservedAtMixin()
    mixin.temporal_context = moment

    assert mixin.observed_at == moment
    assert mixin.is_historic_view is True
    assert mixin.temporal_string == str(moment)


def test_temporal_context_converter_to_python():
    converter = TemporalContextConverter()

    assert converter.to_python("now") is None
    assert converter.to_python("at-20231024T093456Z") == datetime(2023, 10, 24, 9, 34, 56, tzinfo=timezone.utc)


def test_temporal_context_converter_to_url():
    converter = TemporalContextConverter()

    assert converter.to_url(None) == "now"
    assert converter.to_url("now") == "now"
    assert converter.to_url(datetime(2023, 10, 24, 9, 34, 56, tzinfo=timezone.utc)) == "at-20231024T093456Z"


def test_observed_at_historic_view_through_url(rf, client_member, mock_organization_view_octopoes):
    """A historic temporal context in the URL renders a historic object list at that valid time."""
    moment = datetime(2023, 10, 24, 9, 34, 56, tzinfo=timezone.utc)
    kwargs = {"organization_code": client_member.organization.code, "temporal_context": moment}
    url = reverse("ooi_list", kwargs=kwargs)
    request = rf.get(url)
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=1, items=[Network(name="testnetwork")]
    )

    response = OOIListView.as_view()(
        request, organization_code=client_member.organization.code, temporal_context=moment
    )

    assert response.status_code == 200
    assert response.context_data["observed_at"] == moment
    assert response.context_data["historic_view"] is True
