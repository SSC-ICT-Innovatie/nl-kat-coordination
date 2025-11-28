"""Tests for task views and forms"""

from django.contrib.contenttypes.models import ContentType
from pytest_django.asserts import assertContains

from objects.models import Hostname, Network
from plugins.models import Plugin
from tasks.models import ObjectSet, Task, TaskStatus
from tasks.views import ObjectSetCreateView, TaskCancelAllView, TaskCreateView, TaskListView
from tests.conftest import setup_request


def test_task_create_view_with_preselected_hostnames(rf, superuser_member, xtdb, organization):
    network = Network.objects.create(name="internet")
    h1 = Hostname.objects.create(name="test1.com", network=network)
    h2 = Hostname.objects.create(name="test2.com", network=network)

    request = setup_request(
        rf.get("tasks:add_task", query_params={"input_hostnames": [str(h1.pk), str(h2.pk)]}), superuser_member.user
    )
    response = TaskCreateView.as_view()(request)

    assert response.status_code == 200
    # Check that the form has initial data
    assert "input_hostnames" in response.context_data["form"].initial
    initial_hostnames = list(response.context_data["form"].initial["input_hostnames"])
    assert len(initial_hostnames) == 2
    assert h1 in initial_hostnames
    assert h2 in initial_hostnames


def test_task_form_with_object_set(rf, superuser_member, xtdb, organization, mocker):
    mock_run_plugin = mocker.patch("tasks.views.run_plugin_on_object_set")
    mock_run_plugin.return_value = []

    network = Network.objects.create(name="internet")
    h1 = Hostname.objects.create(name="test1.com", network=network, scan_level=2)
    h2 = Hostname.objects.create(name="test2.com", network=network, scan_level=2)

    plugin = Plugin.objects.create(
        name="test", plugin_id="test", oci_image="T", oci_arguments=["{hostname}"], scan_level=2
    )
    plugin.schedule_for(organization)

    hostname_ct = ContentType.objects.get_for_model(Hostname)
    object_set = ObjectSet.objects.create(
        name="Test Set",
        object_type=hostname_ct,
        object_query="",  # All hostnames
        static_objects=[str(h1.pk), str(h2.pk)],
    )

    request = setup_request(
        rf.post(
            "tasks:add_task",
            data={"plugin": str(plugin.pk), "object_set": str(object_set.pk), "organization": str(organization.pk)},
        ),
        superuser_member.user,
    )
    TaskCreateView.as_view()(request)

    assert mock_run_plugin.called
    call_kwargs = mock_run_plugin.call_args[1]
    assert call_kwargs["object_set"] == object_set
    assert call_kwargs["plugin"] == plugin
    assert call_kwargs["organization"] == organization


def test_object_set_form_query_all_checkbox(rf, superuser_member, xtdb):
    hostname_ct = ContentType.objects.get_for_model(Hostname)

    request = setup_request(rf.get("tasks:add_object_set"), superuser_member.user)
    response = ObjectSetCreateView.as_view()(request)
    assert response.status_code == 200

    request = setup_request(
        rf.post(
            "tasks:add_object_set",
            query_params={"object_type": str(hostname_ct.pk)},
            data={
                "name": "All Hostnames",
                "description": "All hostname objects",
                "object_type": str(hostname_ct.pk),
                "query_all": "on",  # Checkbox is checked
                "object_query": "",  # Empty query
                "static_objects": [],
            },
        ),
        superuser_member.user,
    )
    ObjectSetCreateView.as_view()(request)

    # Check that object_query is saved as empty string (not None)
    object_set = ObjectSet.objects.filter(name="All Hostnames").first()
    assert object_set is not None
    assert object_set.object_query == ""


def test_object_set_form_query_none_when_checkbox_unchecked(rf, superuser_member, xtdb):
    """Test that ObjectSetForm saves None when query is empty and checkbox unchecked"""
    hostname_ct = ContentType.objects.get_for_model(Hostname)

    # Create object set with query_all NOT checked and empty query
    request = setup_request(
        rf.post(
            "tasks:add_object_set",
            query_params={"object_type": str(hostname_ct.pk)},
            data={
                "name": "Custom Hostnames",
                "description": "Custom hostname objects",
                "object_type": str(hostname_ct.pk),
                "object_query": "",  # Empty query
                "static_objects": [],
            },
        ),
        superuser_member.user,
    )
    ObjectSetCreateView.as_view()(request)

    # Check that object_query is saved as None
    object_set = ObjectSet.objects.filter(name="Custom Hostnames").first()
    assert object_set is not None
    assert object_set.object_query is None


def test_object_set_two_step_creation(rf, superuser_member, xtdb):
    request = setup_request(rf.get("tasks:add_object_set"), superuser_member.user)
    response = ObjectSetCreateView.as_view()(request)

    assert response.status_code == 200
    assert response.context_data["show_type_selection"] is True

    # Step 2: POST with object_type should redirect with query param
    hostname_ct = ContentType.objects.get_for_model(Hostname)
    request = setup_request(
        rf.post("tasks:add_object_set", data={"object_type": str(hostname_ct.pk)}), superuser_member.user
    )
    response = ObjectSetCreateView.as_view()(request)

    assert response.status_code == 302
    assert f"object_type={hostname_ct.pk}" in response.url

    # Step 3: GET with object_type query param should show full form
    request = setup_request(
        rf.get("tasks:add_object_set", query_params={"object_type": str(hostname_ct.pk)}), superuser_member.user
    )
    response = ObjectSetCreateView.as_view()(request)

    assert response.status_code == 200
    assert response.context_data["show_type_selection"] is False
    assert "object_type" in response.context_data["form"].initial
    assert response.context_data["form"].initial["object_type"] == hostname_ct


def test_object_set_creation_with_preselected_objects(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    h1 = Hostname.objects.create(name="test1.com", network=network)
    h2 = Hostname.objects.create(name="test2.com", network=network)

    hostname_ct = ContentType.objects.get_for_model(Hostname)

    # GET with object_type and objects query params
    request = setup_request(
        rf.get(
            "tasks:add_object_set",
            query_params={"object_type": str(hostname_ct.pk), "objects": [str(h1.pk), str(h2.pk)]},
        ),
        superuser_member.user,
    )
    response = ObjectSetCreateView.as_view()(request)

    assert response.status_code == 200
    assert "static_objects" in response.context_data["form"].initial
    initial_objects = response.context_data["form"].initial["static_objects"]
    assert str(h1.pk) in initial_objects
    assert str(h2.pk) in initial_objects


def test_object_set_type_field_disabled_after_selection(rf, superuser_member, xtdb):
    hostname_ct = ContentType.objects.get_for_model(Hostname)

    request = setup_request(
        rf.get("tasks:add_object_set", query_params={"object_type": str(hostname_ct.pk)}), superuser_member.user
    )
    response = ObjectSetCreateView.as_view()(request)

    assert response.status_code == 200
    # Check that object_type field is disabled
    form = response.context_data["form"]
    assert form.fields["object_type"].disabled is True


def test_task_list_view(rf, superuser, organization, organization_b):
    a = Task.objects.create(organization=organization, type="plugin", data={"plugin_id": "test_plugin"})
    b = Task.objects.create(organization=organization_b, type="plugin", data={"plugin_id": "test_plugin"})

    request = setup_request(rf.get("task_list"), superuser)
    response = TaskListView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, a.pk)
    assertContains(response, b.pk)
    assertContains(response, "test_plugin")


def test_task_cancel_all_view(rf, superuser_member, xtdb, organization, organization_b, mocker):
    mock_cancel = mocker.patch("tasks.models.Task.cancel")

    Task.objects.create(organization=organization, type="plugin", data={}, status=TaskStatus.QUEUED)
    Task.objects.create(organization=organization, type="plugin", data={}, status=TaskStatus.PENDING)
    Task.objects.create(organization=organization, type="plugin", data={}, status=TaskStatus.COMPLETED)
    Task.objects.create(organization=organization_b, type="plugin", data={}, status=TaskStatus.QUEUED)

    request = setup_request(rf.post("task_cancel_all"), superuser_member.user)
    response = TaskCancelAllView.as_view()(request)

    assert response.status_code == 302
    assert "/tasks/" in response.url
    assert mock_cancel.call_count == 3

    mock_cancel.reset_mock()

    request = setup_request(
        rf.post("task_cancel_all", query_params={"organization": [organization.code]}), superuser_member.user
    )
    response = TaskCancelAllView.as_view()(request)

    assert response.status_code == 302
    assert mock_cancel.call_count == 2
