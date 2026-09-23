from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from bytes.auth import ALGORITHM, authenticate_token
from bytes.config import Settings
from tests.loading import load_stub

# Any UUID works — the request never reaches the DB because authenticate_token runs first.
PROTECTED_PATH = "/bytes/boefje_meta/00000000-0000-0000-0000-000000000000"


def test_login_get_token(test_client: TestClient) -> None:
    request = load_stub("login-request.json")

    response = test_client.post("/token", data=request)

    assert response.status_code == 200

    data = response.json()
    assert data["token_type"] == "bearer"
    assert authenticate_token(data["access_token"]) == "test"
    assert datetime.fromisoformat(data["expires_at"]) > datetime.now(timezone.utc)


def test_login_get_token_not_authorized(test_client: TestClient) -> None:
    request = load_stub("login-request.json")
    request["username"] = "nivlac"

    response = test_client.post("/token", data=request)
    assert response.status_code == 401


def test_protected_endpoint_without_authorization_header(test_client: TestClient) -> None:
    response = test_client.get(PROTECTED_PATH)
    assert response.status_code == 401


def test_protected_endpoint_with_malformed_token(test_client: TestClient) -> None:
    response = test_client.get(PROTECTED_PATH, headers={"Authorization": "bearer not-a-jwt"})
    assert response.status_code == 401


def test_protected_endpoint_with_expired_token(test_client: TestClient, settings: Settings) -> None:
    expired = jwt.encode(
        {"sub": "test", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}, settings.secret, algorithm=ALGORITHM
    )
    response = test_client.get(PROTECTED_PATH, headers={"Authorization": f"bearer {expired}"})
    assert response.status_code == 401


def test_protected_endpoint_with_token_signed_by_wrong_secret(test_client: TestClient) -> None:
    forged = jwt.encode(
        {"sub": "test", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "definitely-not-the-real-secret",
        algorithm=ALGORITHM,
    )
    response = test_client.get(PROTECTED_PATH, headers={"Authorization": f"bearer {forged}"})
    assert response.status_code == 401


def test_protected_endpoint_with_token_missing_sub_claim(test_client: TestClient, settings: Settings) -> None:
    no_sub = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, settings.secret, algorithm=ALGORITHM
    )
    response = test_client.get(PROTECTED_PATH, headers={"Authorization": f"bearer {no_sub}"})
    assert response.status_code == 401
