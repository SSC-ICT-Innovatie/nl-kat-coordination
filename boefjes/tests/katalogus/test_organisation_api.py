def test_list(unit_test_client):
    res = unit_test_client.get("/v1/organisations")
    assert res.status_code == 200


def test_get_organisation(unit_test_client):
    res = unit_test_client.get("/v1/organisations/test")
    assert res.status_code == 200


def test_non_existing_organisation(unit_test_client):
    res = unit_test_client.get("/v1/organisations/future-organisation")
    assert res.status_code == 404
    assert "unknown organisation" in res.text.lower()


def test_add_organisation(unit_test_client):
    res = unit_test_client.post("/v1/organisations/", json={"id": "new", "name": "New"})
    assert res.status_code == 201

    res = unit_test_client.get("/v1/organisations")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_delete_organisation(unit_test_client):
    res = unit_test_client.delete("/v1/organisations/test")
    assert res.status_code == 200

    res = unit_test_client.get("/v1/organisations")
    assert res.status_code == 200
    assert len(res.json()) == 0
