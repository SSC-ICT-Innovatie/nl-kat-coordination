import os

import pytest

from boefjes.worker.models import Boefje, Normalizer, Organisation

pytestmark = pytest.mark.skipif(os.environ.get("CI") != "1", reason="Needs a CI database.")


def test_get_local_plugin(test_client, organisation):
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/dns-records")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "dns-records"


def test_create_org(test_client):
    response = test_client.post("/v1/organisations/", json={"id": "test2", "name": "test2"})
    assert response.status_code == 201

    assert test_client.get("/v1/organisations/test2/").json() == {"id": "test2", "name": "test2", "deduplicate": True}


def test_filter_plugins(test_client, organisation):
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins")
    assert len(response.json()) >= 100
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins", params={"plugin_type": "boefje"})
    assert len(response.json()) > 10
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins", params={"state": "true"})
    assert len(response.json()) > 10
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins", params={"limit": 10})
    assert len(response.json()) == 10

    # Test "consumes" and "produces" filters
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins", params={"consumes": "ADRFindingType"})
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == "adr-finding-types"
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins", params={"produces": "Finding"})
    assert len(response.json()) == 27
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins", params={"consumes": "boefje/censys"})
    assert len(response.json()) == 1
    response = test_client.get(
        f"/v1/organisations/{organisation.id}/plugins", params={"consumes": ["ADRFindingType", "Hostname"]}
    )
    assert len(response.json()) == 10

    response = test_client.get(
        f"/v1/organisations/{organisation.id}/plugins", params={"oci_image": "ghcr.io/minvws/openkat/nmap:latest"}
    )
    assert {x["id"] for x in response.json()} == {"nmap", "nmap-udp"}  # Nmap TCP and UDP

    boefje = Boefje(
        id="test_plugin", name="My test boefje", static=False, oci_image="ghcr.io/minvws/openkat/nmap:latest"
    )
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 201

    response = test_client.get(
        f"/v1/organisations/{organisation.id}/plugins", params={"oci_image": "ghcr.io/minvws/openkat/nmap:latest"}
    )
    assert {x["id"] for x in response.json()} == {"nmap", "nmap-udp", "test_plugin"}  # Nmap TCP and UDP


def test_cannot_add_plugin_reserved_id(test_client, organisation):
    boefje = Boefje(id="dns-records", name="My test boefje", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 400
    assert response.json() == {"detail": "Duplicate plugin: a plugin with this id already exists"}

    normalizer = Normalizer(id="kat_nmap_normalize", name="My test normalizer")
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=normalizer.model_dump_json())
    assert response.status_code == 400
    assert response.json() == {"detail": "Duplicate plugin: a plugin with this id already exists"}


def test_add_boefje(test_client, organisation):
    boefje = Boefje(id="test_plugin", name="My test boefje", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 201

    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", json={"a": "b"})
    assert response.status_code == 422

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/?plugin_type=boefje")
    assert len(response.json()) > 10

    boefje_dict = boefje.model_dump()
    boefje_dict["consumes"] = list(boefje_dict["consumes"])
    boefje_dict["produces"] = list(boefje_dict["produces"])

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/test_plugin")
    assert response.json() == boefje_dict


def test_enable_boefje(test_client, organisation, second_organisation):
    test_client.patch(f"/v1/organisations/{organisation.id}/plugins/dns-records", json={"enabled": True})

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/dns-records")
    assert response.json()["enabled"] is True

    response = test_client.get(f"/v1/organisations/{second_organisation.id}/plugins/dns-records")
    assert response.json()["enabled"] is False


def test_run_on(test_client, organisation, second_organisation):
    test_client.patch(f"/v1/organisations/{organisation.id}/plugins/export-to-http-api", json={"enabled": True})

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/export-to-http-api")
    assert response.json()["enabled"] is True
    assert response.json()["run_on"] == ["create", "update"]

    boefje = Boefje(id="test_run_on", name="Run On", static=False, run_on=["create"])
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 201

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/test_run_on")
    assert response.json()["enabled"] is False
    assert response.json()["run_on"] == [x.value for x in boefje.run_on]


def test_cannot_add_static_plugin_with_duplicate_name(test_client, organisation):
    boefje = Boefje(id="test_plugin", name="DNS records", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 400

    boefje = Boefje(id="test_plugin", name="DNS records", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 400
    assert response.json() == {"detail": "Duplicate plugin: a plugin with this name already exists"}


def test_cannot_add_plugin_with_duplicate_name(test_client, organisation):
    boefje = Boefje(id="test_plugin", name="My test boefje", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 201

    boefje = Boefje(id="test_plugin_2", name="My test boefje", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 400
    assert response.json() == {"detail": "Duplicate plugin: a plugin with this name already exists"}

    normalizer = Normalizer(id="test_normalizer", name="My test normalizer", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=normalizer.model_dump_json())
    assert response.status_code == 201

    normalizer = Normalizer(id="test_normalizer_2", name="My test normalizer", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=normalizer.model_dump_json())
    assert response.status_code == 400


def test_delete_boefje(test_client, organisation):
    boefje = Boefje(id="test_plugin", name="My test boefje", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    assert response.status_code == 201

    response = test_client.delete(f"/v1/organisations/{organisation.id}/boefjes/test_plugin")
    assert response.status_code == 204
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/test_plugin")
    assert response.status_code == 404


def test_add_normalizer(test_client, organisation):
    normalizer = Normalizer(id="test_normalizer", name="My test normalizer", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=normalizer.model_dump_json())
    assert response.status_code == 201

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/?plugin_type=normalizer")
    assert len(response.json()) == 58

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/test_normalizer")
    assert response.json() == normalizer.model_dump()


def test_delete_normalizer(test_client, organisation):
    normalizer = Normalizer(id="test_normalizer", name="My test normalizer", static=False)
    response = test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=normalizer.model_dump_json())
    assert response.status_code == 201

    response = test_client.delete(f"/v1/organisations/{organisation.id}/normalizers/test_normalizer")
    assert response.status_code == 204
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/test_normalizer")
    assert response.status_code == 404


def test_update_plugins(test_client, organisation, second_organisation):
    normalizer = Normalizer(id="norm_id", name="My test normalizer")
    boefje = Boefje(id="test_plugin", name="My test boefje", description="123", interval=20)

    test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())
    test_client.patch(f"/v1/organisations/{organisation.id}/plugins/{boefje.id}", json={"enabled": True})
    test_client.patch(f"/v1/organisations/{organisation.id}/boefjes/{boefje.id}", json={"scan_level": 3})
    test_client.patch(f"/v1/organisations/{organisation.id}/boefjes/{boefje.id}", json={"description": "4"})
    test_client.patch(f"/v1/organisations/{organisation.id}/boefjes/{boefje.id}", json={"cron": "5 0 * 8 *"})

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/{boefje.id}")
    assert response.json()["description"] == "4"
    assert response.json()["scan_level"] == 3
    assert response.json()["enabled"] is True
    assert response.json()["scan_level"] == 3
    assert response.json()["interval"] == 20
    assert response.json()["cron"] == "5 0 * 8 *"

    test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=normalizer.model_dump_json())
    test_client.patch(f"/v1/organisations/{organisation.id}/normalizers/{normalizer.id}", json={"version": "v1.2"})

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/{normalizer.id}")
    assert response.json()["version"] == "v1.2"


def test_cannot_create_boefje_with_invalid_schema(test_client, organisation):
    boefje = Boefje(id="test_plugin", name="My test boefje", description="123").model_dump(mode="json")
    boefje["boefje_schema"] = {"$schema": 3}

    r = test_client.post(f"/v1/organisations/{organisation.id}/plugins", json=boefje)
    assert r.status_code == 422


def test_schema_is_taken_from_disk(test_client, organisation, session):
    # creates a database record of dns-records
    test_client.patch(f"/v1/organisations/{organisation.id}/plugins/dns-records", json={"enabled": True})
    session.execute("UPDATE boefje set schema = null where plugin_id = 'dns-records'")
    session.commit()

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/dns-records").json()
    assert response["boefje_schema"] is not None


def test_cannot_set_invalid_cron(test_client, organisation):
    boefje = Boefje(id="test_plugin", name="My test boefje", description="123").model_dump(mode="json")
    boefje["cron"] = "bad format"

    res = test_client.post(f"/v1/organisations/{organisation.id}/plugins", json=boefje)
    assert res.status_code == 422

    boefje = Boefje(id="test_plugin", name="My test boefje")
    test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.json())
    res = test_client.patch(f"/v1/organisations/{organisation.id}/boefjes/{boefje.id}", json={"cron": "bad format"})
    assert res.status_code == 422


def test_update_boefje_schema(test_client, organisation):
    boefje = Boefje(id="test_plugin", name="My test boefje", description="123")
    test_client.post(f"/v1/organisations/{organisation.id}/plugins", content=boefje.model_dump_json())

    r = test_client.patch(
        f"/v1/organisations/{organisation.id}/boefjes/{boefje.id}", json={"boefje_schema": {"$schema": 3}}
    )
    assert r.status_code == 422

    valid_schema = {
        "title": "Arguments",
        "type": "object",
        "properties": {"MY_KEY": {"title": "MY_KEY", "type": "integer"}},
        "required": [],
    }
    r = test_client.patch(
        f"/v1/organisations/{organisation.id}/boefjes/{boefje.id}", json={"boefje_schema": valid_schema}
    )
    assert r.status_code == 204

    schema = test_client.get(f"/v1/organisations/{organisation.id}/plugins/{boefje.id}/schema.json").json()
    assert schema == valid_schema

    api_boefje = test_client.get(f"/v1/organisations/{organisation.id}/plugins/{boefje.id}").json()
    assert api_boefje["boefje_schema"] == valid_schema

    r = test_client.patch(
        f"/v1/organisations/{organisation.id}/boefjes/dns-records", json={"boefje_schema": valid_schema}
    )
    assert r.status_code == 404


def test_cannot_update_static_plugins(test_client, organisation):
    r = test_client.patch(f"/v1/organisations/{organisation.id}/boefjes/dns-records", json={"id": "4", "version": "s"})
    assert r.status_code == 404
    r = test_client.patch(f"/v1/organisations/{organisation.id}/boefjes/dns-records", json={"name": "Overwrite name"})
    assert r.status_code == 404

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/dns-records")
    assert response.json()["name"] == "DNS records"
    assert response.json()["version"] is None
    assert response.json()["id"] == "dns-records"

    test_client.patch(f"/v1/organisations/{organisation.id}/plugins/dns-records", json={"enabled": True})
    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/dns-records")
    assert response.json()["enabled"] is True

    response = test_client.patch(f"/v1/organisations/{organisation.id}/boefjes/dns-records", json={"version": "v1.2"})
    assert response.status_code == 403

    response = test_client.get(f"/v1/organisations/{organisation.id}/plugins/dns-records")
    assert response.json()["version"] != "v1.2"


def test_basic_settings_api(test_client, organisation):
    plug = "dns-records"

    test_client.put(f"/v1/organisations/{organisation.id}/{plug}/settings", json={"new": "settings", "with integer": 5})
    response = test_client.get(f"/v1/organisations/{organisation.id}/{plug}/settings")
    assert response.json() == {"new": "settings", "with integer": 5}

    test_client.put(f"/v1/organisations/{organisation.id}/{plug}/settings", json={"with integer": 8})
    response = test_client.get(f"/v1/organisations/{organisation.id}/{plug}/settings")
    assert response.json() == {"with integer": 8}

    test_client.delete(f"/v1/organisations/{organisation.id}/{plug}/settings")
    response = test_client.get(f"/v1/organisations/{organisation.id}/{plug}/settings")
    assert response.json() == {}

    nmap_ports = "nmap-ports"
    response = test_client.put(f"/v1/organisations/{organisation.id}/{nmap_ports}/settings", json={"PORTS": "80"})
    assert response.status_code == 200
    assert test_client.get(f"/v1/organisations/{organisation.id}/{nmap_ports}/settings").json() == {"PORTS": "80"}


def test_clone_settings_and_config_api_shows_both(test_client, organisation):
    plug = "dns-records"

    # Set a setting on the first organisation and enable dns-records
    test_client.put(
        f"/v1/organisations/{organisation.id}/{plug}/settings",
        json={"test_key": "test value", "test_key_2": "test value 2"},
    )
    test_client.patch(f"/v1/organisations/{organisation.id}/plugins/{plug}", json={"enabled": True})
    test_client.patch(f"/v1/organisations/{organisation.id}/plugins/kat_dns_normalize", json={"enabled": False})

    assert test_client.get(f"/v1/organisations/{organisation.id}/{plug}/settings").json() == {
        "test_key": "test value",
        "test_key_2": "test value 2",
    }
    assert test_client.get(f"/v1/organisations/{organisation.id}/plugins/{plug}").json()["enabled"] is True

    # Add the second organisation
    new_org_id = "org2"
    org2 = Organisation(id=new_org_id, name="Second test Organisation")
    test_client.post("/v1/organisations/", content=org2.model_dump_json())
    test_client.put(f"/v1/organisations/{new_org_id}/{plug}/settings", json={"test_key": "second value"})

    # Show that the second organisation has no settings and dns-records is not enabled
    assert test_client.get(f"/v1/organisations/{new_org_id}/{plug}/settings").json() == {"test_key": "second value"}
    assert test_client.get(f"/v1/organisations/{new_org_id}/plugins/{plug}").json()["enabled"] is False

    # Enable two boefjes that should get disabled by the cloning
    test_client.patch(f"/v1/organisations/{new_org_id}/plugins/nmap", json={"enabled": True})
    assert test_client.get(f"/v1/organisations/{new_org_id}/plugins/nmap").json()["enabled"] is True

    # Call the clone endpoint
    test_client.post(f"/v1/organisations/{organisation.id}/settings/clone/{new_org_id}")

    # Verify that all settings are copied
    response = test_client.get(f"/v1/organisations/{new_org_id}/{plug}/settings")
    assert response.json() == {"test_key": "test value", "test_key_2": "test value 2"}

    # And that the enabled boefje from the original organisation got enabled
    response = test_client.get(f"/v1/organisations/{new_org_id}/plugins/{plug}")
    assert response.json()["enabled"] is True

    # And the originally enabled boefje got disabled
    response = test_client.get(f"/v1/organisations/{new_org_id}/plugins/nmap")
    assert response.json()["enabled"] is False

    # And the originally disabled normalizer got disabled
    response = test_client.get(f"/v1/organisations/{new_org_id}/plugins/kat_dns_normalize")
    assert response.json()["enabled"] is False

    # Assert we can fetch the settings with the new configs API
    expected = [
        {
            "boefje_id": "dns-records",
            "enabled": True,
            "id": 8,
            "organisation_id": "test",
            "settings": {"test_key": "test value", "test_key_2": "test value 2"},
            "duplicates": [],
        },
        {"boefje_id": "nmap", "enabled": False, "id": 10, "organisation_id": "org2", "settings": {}, "duplicates": []},
        {
            "boefje_id": "dns-records",
            "enabled": True,
            "id": 9,
            "organisation_id": "org2",
            "settings": {"test_key": "test value", "test_key_2": "test value 2"},
            "duplicates": [],
        },
    ]
    assert test_client.get("/v1/configs").json() == expected
    assert test_client.get("/v1/configs", params={"limit": "2"}).json() == [expected[0], expected[1]]
    assert test_client.get("/v1/configs", params={"organisation_id": "test"}).json() == [expected[0]]
    assert test_client.get("/v1/configs", params={"organisation_id": "org2"}).json() == [expected[2], expected[1]]
    assert test_client.get("/v1/configs", params={"organisation_id": "org2", "boefje_id": "nmap"}).json() == [
        expected[1]
    ]
    assert test_client.get("/v1/configs", params={"boefje_id": "dns-records"}).json() == [expected[0], expected[2]]
    assert test_client.get("/v1/configs", params={"enabled": True}).json() == [expected[0], expected[2]]

    expected_with_duplicates = [
        {
            "boefje_id": "dns-records",
            "enabled": True,
            "id": 8,
            "organisation_id": "test",
            "settings": {"test_key": "test value", "test_key_2": "test value 2"},
            "duplicates": [expected[2]],
        },
        {
            "boefje_id": "dns-records",
            "enabled": True,
            "id": 9,
            "organisation_id": "org2",
            "settings": {"test_key": "test value", "test_key_2": "test value 2"},
            "duplicates": [expected[0]],
        },
    ]
    assert test_client.get(
        "/v1/configs", params={"boefje_id": "dns-records", "organisation_id": "test", "with_duplicates": True}
    ).json() == [expected_with_duplicates[0]]

    assert test_client.get(
        "/v1/configs", params={"boefje_id": "dns-records", "organisation_id": "org2", "with_duplicates": True}
    ).json() == [expected_with_duplicates[1]]

    org2.deduplicate = False
    test_client.put("/v1/organisations/", content=org2.model_dump_json())
    assert test_client.get(f"/v1/organisations/{org2.id}").json()["deduplicate"] is False

    assert test_client.get(
        "/v1/configs", params={"boefje_id": "dns-records", "organisation_id": "test", "with_duplicates": True}
    ).json() == [expected[0]]
