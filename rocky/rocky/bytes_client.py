import json
import uuid
from base64 import b64decode, b64encode
from collections.abc import Set
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from django.conf import settings

from octopoes.api.models import Declaration
from rocky.health import ServiceHealth
from rocky.scheduler import Boefje, BoefjeMeta, Normalizer, NormalizerMeta, RawData

logger = structlog.get_logger("bytes_client")


class BytesClient:
    # More than 100 raw files per Boefje run is very unlikely at this stage, but eventually we can start paginating
    RAW_FILES_LIMIT = 100

    def __init__(self, base_url: str, username: str, password: str, organization: str | None):
        self.credentials = {"username": username, "password": password}
        self.session = httpx.Client(base_url=base_url, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT)
        self.organization = organization

    def health(self) -> ServiceHealth:
        response = self.session.get("/health")
        response.raise_for_status()

        return ServiceHealth.model_validate(response.json())

    @staticmethod
    def raw_from_declarations(declarations: list[Declaration]) -> bytes:
        json_string = f"[{','.join([declaration.model_dump_json() for declaration in declarations])}]"

        return json_string.encode("utf-8")

    def add_manual_proof(
        self, normalizer_id: uuid.UUID, raw: bytes, manual_mime_types: Set[str] = frozenset({"manual/ooi"})
    ) -> None:
        """Per convention for a generic normalizer, we add a raw list of declarations, not a single declaration"""

        self.login()

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
        self.login()

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
            "/bytes/boefje_meta", content=boefje_meta.model_dump_json(), headers={"content-type": "application/json"}
        )
        response.raise_for_status()

    def _save_normalizer_meta(self, normalizer_meta: NormalizerMeta) -> None:
        response = self.session.post(
            "/bytes/normalizer_meta",
            content=normalizer_meta.model_dump_json(),
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

        return [(file["name"], b64decode(file["content"])) for file in response.json().get("files", [])]

    def get_raws_all(self, raw_ids: list[str]) -> dict[str, dict[str, Any]]:
        params: dict[str, str | int | list[str]] = {"limit": len(raw_ids), "raw_ids": raw_ids}

        response = self.session.get("/bytes/raws", params=params)
        response.raise_for_status()
        try:
            return {
                file["name"]: json.loads(b64decode(file["content"]).decode("utf-8"))
                for file in response.json().get("files", [])
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

    def login(self):
        self.session.headers.update(self._authorization_header())

    def _authorization_header(self) -> dict[str, str]:
        return {"Authorization": f"bearer {self._get_token()}"}

    def _get_token(self) -> str:
        response = self.session.post(
            "/token", data=self.credentials, headers={"content-type": "application/x-www-form-urlencoded"}
        )

        return response.json()["access_token"]


def get_bytes_client(organization: str | None) -> BytesClient:
    return BytesClient(settings.BYTES_API, settings.BYTES_USERNAME, settings.BYTES_PASSWORD, organization)
