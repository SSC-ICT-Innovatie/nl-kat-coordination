import json
import uuid
from base64 import b64decode, b64encode
from collections.abc import Generator, Sequence, Set
from datetime import datetime, timezone
from functools import cached_property
from typing import Any

import httpx
import structlog
from django.conf import settings

from octopoes.api.models import Declaration
from rocky.health import ServiceHealth
from rocky.scheduler import Boefje, BoefjeMeta, Normalizer, NormalizerMeta, RawData

logger = structlog.get_logger("bytes_client")


class NoAuth(httpx.Auth):
    def auth_flow(self, request):
        yield request


class TokenAuth(httpx.Auth):
    def __init__(self, client: "BytesClient"):
        self.client = client

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        # Attach token
        request.headers["Authorization"] = f"bearer {self.client.token}"

        response = yield request

        # If unauthorized, refresh token and retry once
        if response.status_code in (401, 403):
            logger.info("Bytes token expired or invalid, refreshing and retrying request")
            self.client._invalidate_token()

            # Try to get a new token (may raise)
            request.headers["Authorization"] = f"bearer {self.client.token}"

            yield request  # retry once


class BytesClient:
    # More than 100 raw files per Boefje run is very unlikely at this stage, but eventually we can start paginating
    RAW_FILES_LIMIT = 100

    def __init__(self, base_url: str, username: str, password: str, organization: str | None):
        self.credentials = {"username": username, "password": password}
        self.session = httpx.Client(
            base_url=base_url, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT, auth=TokenAuth(self)
        )
        self.organization = organization

    def health(self) -> ServiceHealth:
        response = self.session.get("/health")
        response.raise_for_status()

        return ServiceHealth.model_validate(response.json())

    @staticmethod
    def raw_from_declarations(declarations: list[Declaration]) -> bytes:
        return json.dumps([d.model_dump(mode="json") for d in declarations]).encode("utf-8")

    def add_manual_proof(
        self, normalizer_id: uuid.UUID, raw: bytes, manual_mime_types: Set[str] = frozenset({"manual/ooi"})
    ) -> None:
        """Per convention for a generic normalizer, we add a raw list of declarations, not a single declaration"""

        boefje_meta = BoefjeMeta(
            id=uuid.uuid4(),
            boefje=Boefje(id="manual"),
            input_ooi=None,
            arguments={},
            organization=self.organization,
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
        )

        self._save_boefje_meta(boefje_meta)
        all_mime_types = {"boefje/manual"}.union(manual_mime_types)
        raw_id = self._save_raw(boefje_meta.id, raw, all_mime_types)

        self._save_normalizer_meta(
            NormalizerMeta(
                id=normalizer_id,
                raw_data=RawData(
                    id=uuid.UUID(raw_id),
                    boefje_meta=boefje_meta,
                    mime_types=[{"value": mime_type} for mime_type in all_mime_types],
                ),
                normalizer=Normalizer(id="normalizer/manual"),
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
            )
        )

    def upload_raw(
        self,
        raw: bytes,
        manual_mime_types: set[str],
        input_ooi: str | None = None,
        input_dict: dict | None = None,
        valid_time: datetime | None = None,
    ) -> str:
        boefje_meta = BoefjeMeta(
            id=uuid.uuid4(),
            boefje=Boefje(id="manual"),
            input_ooi=input_ooi,
            arguments={"input": input_dict} if input_dict else {},
            organization=self.organization,
            started_at=valid_time or datetime.now(timezone.utc),
            ended_at=valid_time or datetime.now(timezone.utc),
        )

        self._save_boefje_meta(boefje_meta)
        raw_id = self._save_raw(boefje_meta.id, raw, {"boefje/manual"}.union(manual_mime_types))

        logger.info("Uploaded raw data", raw_id=raw_id, organization=self.organization)

        return raw_id

    def _save_boefje_meta(self, boefje_meta: BoefjeMeta) -> None:
        response = self.session.post(
            "/bytes/boefje_meta", json=boefje_meta.model_dump(mode="json"), headers={"content-type": "application/json"}
        )
        response.raise_for_status()

    def _save_normalizer_meta(self, normalizer_meta: NormalizerMeta) -> None:
        response = self.session.post(
            "/bytes/normalizer_meta",
            json=normalizer_meta.model_dump(mode="json"),
            headers={"content-type": "application/json"},
        )

        response.raise_for_status()

    def _save_raw(self, boefje_meta_id: uuid.UUID, raw: bytes, mime_types: Set[str] = frozenset()) -> str:
        file_name = "raw"  # The name provides a key for all ids returned, so this is arbitrary as we only upload 1 file

        response = self.session.post(
            "/bytes/raw",
            json={"files": [{"name": file_name, "content": b64encode(raw).decode(), "tags": list(mime_types)}]},
            params={"boefje_meta_id": str(boefje_meta_id)},
        )

        response.raise_for_status()

        return response.json()[file_name]

    def get_raw(self, raw_id: str) -> bytes:
        # Note: we assume organization permissions are handled before requesting raw data.

        response = self.session.get(f"/bytes/raw/{raw_id}")
        response.raise_for_status()

        return response.content

    def get_raws(self, organization_code: str, raw_ids: list[uuid.UUID | str]) -> list[tuple[str, bytes]]:
        params: dict[str, str | int | list[str]] = {
            "limit": len(raw_ids),
            "organization": organization_code,
            "raw_ids": [str(raw_id) for raw_id in raw_ids],
        }

        response = self.session.get("/bytes/raws", params=params)
        response.raise_for_status()

        return [(rawfile["name"], b64decode(rawfile["content"])) for rawfile in response.json().get("files", [])]

    def get_raws_all(self, raw_ids: list[str]) -> dict[str, dict[str, Any]]:
        params: dict[str, str | int | list[str]] = {"limit": len(raw_ids), "raw_ids": raw_ids}

        response = self.session.get("/bytes/raws", params=params)
        response.raise_for_status()
        try:
            return {
                rawfile["name"]: json.loads(b64decode(rawfile["content"]).decode("utf-8"))
                for rawfile in response.json().get("files", [])
            }
        except httpx.ReadTimeout:
            return {}

    def get_raw_metas(self, boefje_meta_id: uuid.UUID, organization_code: str) -> list:
        # More than 100 raw files per Boefje run is very unlikely at this stage, but eventually we can start paginating

        params: dict[str, str | int] = {
            "boefje_meta_id": str(boefje_meta_id),
            "limit": self.RAW_FILES_LIMIT,
            "organization": str(self.organization),
        }

        response = self.session.get("/bytes/raw", params=params)
        response.raise_for_status()

        metas = response.json()
        metas = [raw_meta for raw_meta in metas if raw_meta["boefje_meta"]["organization"] == organization_code]
        if len(metas) >= self.RAW_FILES_LIMIT:
            logger.warning("Reached raw file limit for current view.")

        return metas

    def get_normalizer_meta(self, normalizer_meta_id: uuid.UUID) -> dict:
        # Note: we assume organization permissions are handled before requesting raw data.

        response = self.session.get(f"/bytes/normalizer_meta/{normalizer_meta_id}")
        response.raise_for_status()

        return response.json()

    def get_normalizer_metas(self, normalizer_metas: Sequence[uuid.UUID | str]) -> dict:
        # Note: we assume organization permissions are handled before requesting raw data.

        params: dict[str, int | list[str]] = {
            "limit": len(normalizer_metas),
            "normalizer_metas": [str(normalizer_meta_id) for normalizer_meta_id in normalizer_metas],
        }
        response = self.session.get("/bytes/normalizer_metas", params=params)
        response.raise_for_status()

        return response.json()

    @cached_property
    def token(self) -> str:
        return self._get_token()

    def _invalidate_token(self):
        if "token" in self.__dict__:
            del self.__dict__["token"]

    def _get_token(self) -> str:
        # this request should not try to use the auth provider, as that would cause a loop
        response = self.session.post(
            "/token",
            data=self.credentials,
            headers={"content-type": "application/x-www-form-urlencoded"},
            auth=NoAuth(),
        )
        response.raise_for_status()  # fail loudly on bad login
        return response.json()["access_token"]


def get_bytes_client(organization: str | None) -> BytesClient:
    return BytesClient(settings.BYTES_API, settings.BYTES_USERNAME, settings.BYTES_PASSWORD, organization)
