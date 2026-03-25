from datetime import datetime, timedelta, timezone

from django.urls import resolve, reverse
from tools.forms.base import ObservedAtForm

from octopoes.models.ooi.network import Network
from octopoes.models.pagination import Paginated
from octopoes.models.types import OOIType
from rocky.views.mixins import ObservedAtMixin
from rocky.views.ooi_list import OOIListView
from tests.conftest import setup_request


def test_observed_at_no_value(mocker):
    mock_mixin_datetime = mocker.patch("rocky.views.mixins.datetime")
    mock_request = mocker.Mock()
    mock_request.GET = {}
    mock_request.POST = {}
    now = datetime(2023, 10, 24, 9, 34, 56, 316699, tzinfo=timezone.utc)
    mock_mixin_datetime.now.return_value = now

    observed_at = ObservedAtMixin()
    observed_at.request = mock_request
    assert observed_at.observed_at == now


def test_observed_at_date(mocker):
    mock_request = mocker.Mock()
    mock_request.GET = {"observed_at": "2023-10-24"}

    observed_at = ObservedAtMixin()
    observed_at.request = mock_request
    assert observed_at.observed_at == datetime(2023, 10, 24, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_observed_at_datetime(mocker):
    mock_request = mocker.Mock()
    mock_request.GET = {"observed_at": "2023-10-24T09:34:56"}

    observed_at = ObservedAtMixin()
    observed_at.request = mock_request
    assert observed_at.observed_at == datetime(2023, 10, 24, 9, 34, 56, 0, tzinfo=timezone.utc)


def test_observed_at_datetime_with_timezone(mocker):
    mock_request = mocker.Mock()
    mock_request.GET = {"observed_at": "2023-10-24T11:34:56+02:00"}

    observed_at = ObservedAtMixin()
    observed_at.request = mock_request
    assert observed_at.observed_at == datetime(2023, 10, 24, 9, 34, 56, 0, tzinfo=timezone.utc)


def test_observed_at_future_date(rf, client_member, mock_organization_view_octopoes):
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("ooi_list", kwargs=kwargs)

    day_plus_1_in_future = (datetime.now(tz=timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    request = rf.get(url, {"observed_at": day_plus_1_in_future})
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list.return_value = Paginated[OOIType](
        count=200, items=[Network(name="testnetwork")] * 150
    )

    _ = OOIListView.as_view()(request, organization_code=client_member.organization.code)

    messages = list(request._messages)
    assert messages[0].message == "The selected date is in the future."

    form = ObservedAtForm(data=request.GET)
    assert form.is_valid()
