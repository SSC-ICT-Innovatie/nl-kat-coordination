from datetime import datetime, timedelta

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives._serialization import Encoding, NoEncryption, PrivateFormat
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.db.models import Q

from files.models import File
from openkat.auth.jwt_auth import JWTTokenAuthentication
from tests.conftest import JSONAPIClient


def test_jwt_access(organization):
    client = JSONAPIClient(raise_request_exception=True)
    token = JWTTokenAuthentication.generate({})
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    response = client.get("/api/v1/file/")
    assert response.status_code == 403
    assert response.json() == {
        "errors": [
            {"attr": None, "code": "permission_denied", "detail": "You do not have permission to perform this action."}
        ],
        "type": "client_error",
    }

    token = JWTTokenAuthentication.generate({"files.view_file": {}})
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    response = client.get("/api/v1/file/")
    assert response.status_code == 200
    assert response.json()["count"] == 0

    response = client.get("/api/v1/objects/network/")
    assert response.status_code == 403

    perms = {
        f"{ct}.{name}": None
        for ct, name in Permission.objects.filter(
            ~Q(codename__contains="organization"), Q(content_type__app_label="objects")
        ).values_list("content_type__app_label", "codename")
    }

    token = JWTTokenAuthentication.generate({"files.view_file": {}} | perms)
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    response = client.get("/api/v1/objects/network/")
    assert response.status_code == 200

    response = client.post("/api/v1/objects/")
    assert response.status_code == 201


def test_jwt_malicious_token(organization):
    client = JSONAPIClient(raise_request_exception=True)
    token = JWTTokenAuthentication.generate({"files.view_file": {}})
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    response = client.get("/api/v1/file/")
    assert response.status_code == 200

    now = datetime.now()
    token_data = {
        "permissions": {"files.view_file": {}},
        "iat": now.timestamp(),
        "exp": (now + timedelta(minutes=15)).timestamp(),
    }

    # 1024 is way faster to generate in a test than e.g. 4096
    wrong_private_key = rsa.generate_private_key(65537, 1024, default_backend()).private_bytes(  # noqa: S505
        encoding=Encoding.PEM, format=PrivateFormat.PKCS8, encryption_algorithm=NoEncryption()
    )
    token = jwt.encode(token_data, wrong_private_key, algorithm="RS256")
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    response = client.get("/api/v1/file/")
    assert response.status_code == 401
    assert response.json() == {
        "errors": [{"attr": None, "code": "authentication_failed", "detail": "Invalid token."}],
        "type": "client_error",
    }


def test_jwt_object_permission(organization):
    f1 = File.objects.create(file=ContentFile("first\n", "f1.txt"), type="txt")
    f2 = File.objects.create(file=ContentFile("second\n", "f2.txt"), type="txt")

    client = JSONAPIClient(raise_request_exception=True)
    token = JWTTokenAuthentication.generate({"files.view_file": {"pks": [f1.pk]}})
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    response = client.get("/api/v1/file/")
    assert response.status_code == 200

    response = client.get(f"/api/v1/file/{f1.pk}/download/")
    assert response.status_code == 403

    token = JWTTokenAuthentication.generate(
        {"files.view_file": {"pks": [f1.pk]}, "files.download_file": {"pks": [f1.pk]}}
    )
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    response = client.get(f"/api/v1/file/{f1.pk}/download/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-length"] == str(f1.file.size)
    assert response.headers["content-disposition"] == 'attachment; filename="f1.txt"'
    assert response.file.read() == b"first\n"

    response = client.get(f"/api/v1/file/{f1.pk}/")
    assert response.status_code == 200
    assert response.json() == {
        "created_at": f1.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "file": "http://testserver/media/" + str(f1.file),
        "id": f1.pk,
        "organizations": [],
        "task_result": None,
        "type": "txt",
    }

    response = client.get(f"/api/v1/file/{f2.pk}/")
    assert response.status_code == 403
    assert response.json() == {
        "errors": [
            {"attr": None, "code": "permission_denied", "detail": "You do not have permission to perform this action."}
        ],
        "type": "client_error",
    }

    response = client.post("/api/v1/file/", json={})
    assert response.status_code == 403

    response = client.get(f"/api/v1/file/{f2.pk}/download/")
    assert response.status_code == 403


def test_jwt_file_search_permission(organization):
    f1 = File.objects.create(file=ContentFile("first\n", "f1.txt"), type="abc")
    File.objects.create(file=ContentFile("second\n", "f2.txt"), type="def")

    client = JSONAPIClient(raise_request_exception=True)
    token = JWTTokenAuthentication.generate({"files.view_file": {"pks": [f1.pk], "search": ["ab"], "limit": "1"}})
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    response = client.get("/api/v1/file/", data={"ordering": "-created_at", "limit": "1", "search": "ab"})
    assert response.status_code == 200

    response = client.get(f"/api/v1/file/{f1.pk}/")
    assert response.status_code == 200

    response = client.get("/api/v1/file/", data={"ordering": "-created_at", "limit": "2", "search": "ab"})
    assert response.status_code == 403
    assert response.json() == {
        "errors": [
            {"attr": None, "code": "permission_denied", "detail": "You do not have permission to perform this action."}
        ],
        "type": "client_error",
    }

    response = client.get("/api/v1/file/", data={"ordering": "-created_at", "limit": "1", "search": "ef"})
    assert response.status_code == 403
    assert response.json() == {
        "errors": [
            {"attr": None, "code": "permission_denied", "detail": "You do not have permission to perform this action."}
        ],
        "type": "client_error",
    }
