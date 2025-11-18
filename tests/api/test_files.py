from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile

from files.models import File
from tasks.models import TaskResult


def test_file_list_api(drf_client, xtdb, organization):
    assert drf_client.get("/api/v1/file/").json()["count"] == 0

    file = File.objects.create(type="json")
    file.file.save("test.json", BytesIO(b'{"test": "data"}'))
    file.organizations.add(organization)

    response = drf_client.get("/api/v1/file/").json()
    assert response["count"] == 1
    assert response["results"][0]["type"] == "json"
    assert response["results"][0]["id"] == file.id

    response = drf_client.get(f"/api/v1/file/{file.pk}/download/")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.headers["content-length"] == str(file.file.size)
    assert response.headers["content-disposition"] == 'attachment; filename="test.json"'
    assert response.file.read() == b'{"test": "data"}'


def test_file_create_api(drf_client, xtdb):
    test_file = SimpleUploadedFile("api_test.json", b'{"created": "via API"}', content_type="application/json")
    response = drf_client.post("/api/v1/file/", data={"file": test_file}, format="multipart")
    assert response.status_code == 201

    file_id = response.json()["id"]
    file = File.objects.get(pk=file_id)
    assert file.type == "json"


def test_file_retrieve_api(drf_client, xtdb, organization):
    file = File.objects.create(type="pdf")
    file.file.save("test.pdf", BytesIO(b"%PDF-1.4"))
    file.organizations.add(organization)

    response = drf_client.get(f"/api/v1/file/{file.id}/")
    assert response.json()["id"] == file.id
    assert response.json()["type"] == "pdf"


def test_file_update_api(drf_client, xtdb, organization):
    file = File.objects.create(type="json")
    file.file.save("test.json", BytesIO(b"{}"))
    file.organizations.add(organization)

    response = drf_client.patch(f"/api/v1/file/{file.id}/", json={"type": "txt"})
    assert response.status_code == 200

    file.refresh_from_db()
    assert file.type == "txt"


def test_file_delete_api(drf_client, xtdb, organization):
    file = File.objects.create(type="json")
    file.file.save("test.json", BytesIO(b"{}"))
    file.organizations.add(organization)

    response = drf_client.delete(f"/api/v1/file/{file.id}/")
    assert response.status_code == 204
    assert File.objects.filter(pk=file.id).count() == 0


def test_file_type_filter(drf_client, xtdb, organization):
    for i in range(3):
        json_file = File.objects.create(type="json")
        json_file.file.save(f"test{i}.json", BytesIO(b"{}"))
        json_file.organizations.add(organization)

    for i in range(2):
        pdf_file = File.objects.create(type="pdf")
        pdf_file.file.save(f"test{i}.pdf", BytesIO(b"%PDF"))
        pdf_file.organizations.add(organization)

    response = drf_client.get("/api/v1/file/?type=json")
    assert response.json()["count"] == 3

    response = drf_client.get("/api/v1/file/?type=pdf")
    assert response.json()["count"] == 2

    response = drf_client.get("/api/v1/file/")
    assert response.json()["count"] == 5


def test_file_with_task_result(drf_client, task_db, xtdb):
    """Test creating a file and linking it to a task via task_id query parameter"""
    test_file = SimpleUploadedFile("task_result.json", b'{"task": "result"}', content_type="application/json")

    response = drf_client.post(f"/api/v1/file/?task_id={task_db.id}", data={"file": test_file}, format="multipart")
    assert response.status_code == 201

    file_id = response.json()["id"]

    task_result = TaskResult.objects.filter(file_id=file_id, task_id=task_db.id).first()
    assert task_result is not None
    assert task_result.file.id == file_id
    assert task_result.task.id == task_db.id


def test_file_without_task_result(drf_client, xtdb):
    test_file = SimpleUploadedFile("no_task.json", b'{"no": "task"}', content_type="application/json")
    response = drf_client.post("/api/v1/file/", data={"file": test_file}, format="multipart")
    assert response.status_code == 201

    file_id = response.json()["id"]

    assert TaskResult.objects.filter(file_id=file_id).count() == 0


def test_file_organization_relationship(xtdb, organization):
    file = File.objects.create(type="json")
    file.file.save("org_a.json", BytesIO(b'{"org": "a"}'))
    file.organizations.add(organization)

    assert file.organizations.count() == 1
    assert file.organizations.first().id == organization.id


def test_file_multiple_organizations(xtdb, organization, organization_b):
    file = File.objects.create(type="json")
    file.file.save("multi_org.json", BytesIO(b'{"multi": "org"}'))
    file.organizations.add(organization, organization_b)

    assert file.organizations.count() == 2
    org_ids = set(file.organizations.values_list("id", flat=True))
    assert org_ids == {organization.id, organization_b.id}


def test_bulk_file_creation(drf_client, xtdb):
    for i in range(5):
        test_file = SimpleUploadedFile(f"test{i}.json", b'{"test": "data"}', content_type="application/json")
        response = drf_client.post("/api/v1/file/", data={"file": test_file}, format="multipart")
        assert response.status_code == 201

    assert File.objects.count() == 5
