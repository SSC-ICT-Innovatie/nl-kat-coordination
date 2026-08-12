from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from boto3 import set_stream_logger as set_boto3_stream_logger
from boto3.session import Session as BotoSession

from bytes.config import Settings
from bytes.models import BoefjeMeta, RawData
from bytes.raw.middleware import FileMiddleware, make_middleware
from bytes.repositories.raw_repository import BytesFileNotFoundException, RawRepository

logger = structlog.get_logger(__name__)


if TYPE_CHECKING:
    from mypy_boto3_s3.service_resource import Bucket


def create_raw_repository(settings: Settings) -> RawRepository:
    if settings.s3_bucket_name or settings.s3_bucket_prefix:
        return S3RawRepository(
            make_middleware(),
            settings.bucket_per_org,
            settings.s3_bucket_prefix or "OpenKAT-",
            settings.s3_bucket_name or "OpenKAT",
        )
    else:
        return FileRawRepository(
            settings.data_dir,
            make_middleware(),
            folder_permissions=int(settings.folder_permission, 8),
            file_permissions=int(settings.file_permission, 8),
        )


class FileRawRepository(RawRepository):
    UUID_INDEX = 3  # To reduce the number of subdirectories based on the uuid, see self._index()

    def __init__(
        self,
        base_path: Path,
        file_middleware: FileMiddleware,
        *,
        folder_permissions: int = 0o750,
        file_permissions: int = 0o640,
    ) -> None:
        self.base_path = base_path
        self.file_middleware = file_middleware
        self._folder_permissions = folder_permissions
        self._file_permissions = file_permissions

    def save_raw(self, raw_id: UUID, raw: RawData) -> None:
        file_path = self._raw_file_path(raw_id, raw.boefje_meta)

        for parent in reversed(file_path.parents):
            parent.mkdir(exist_ok=True, mode=self._folder_permissions)

        contents = self.file_middleware.encode(raw.value)

        logger.info("Writing raw data with id %s to disk", raw_id)
        file_path.write_bytes(contents)
        file_path.chmod(self._file_permissions)

    def get_raw(self, raw_id: UUID, boefje_meta: BoefjeMeta) -> RawData:
        file_path = self._raw_file_path(raw_id, boefje_meta)

        if not file_path.exists():
            raise BytesFileNotFoundException()

        contents = file_path.read_bytes()
        return RawData(value=self.file_middleware.decode(contents), boefje_meta=boefje_meta)

    def get_raws(self, raw_metas_pairs: list[tuple[UUID, BoefjeMeta]]) -> list[tuple[UUID, RawData]]:
        try:
            raws = [
                (raw_id, self._raw_file_path(raw_id, boefje_meta).read_bytes(), boefje_meta)
                for raw_id, boefje_meta in raw_metas_pairs
            ]
        except FileNotFoundError:
            raise BytesFileNotFoundException()

        return [
            (raw_id, RawData(value=self.file_middleware.decode(raw), boefje_meta=boefje_meta))
            for raw_id, raw, boefje_meta in raws
        ]

    def _raw_file_path(self, raw_id: UUID, boefje_meta: BoefjeMeta) -> Path:
        return self.base_path / boefje_meta.organization / self._index(raw_id) / str(raw_id)

    def _index(self, raw_id: UUID) -> str:
        return str(raw_id)[: self.UUID_INDEX]


class S3RawRepository(RawRepository):
    def __init__(
        self, file_middleware: FileMiddleware, bucket_per_org: bool, s3_bucket_prefix: str, s3_bucket_name: str
    ) -> None:
        self._file_middleware = file_middleware
        self.bucket_per_org = bucket_per_org
        self.s3_bucket_prefix = s3_bucket_prefix
        self.s3_bucket_name = s3_bucket_name

        set_boto3_stream_logger("", logging.WARNING)
        self._s3resource = BotoSession().resource("s3")

    def get_or_create_bucket(self, organization: str) -> Bucket:
        # Create a bucket, and if it exists already return that instead
        bucket_name = f"{self.s3_bucket_prefix}{organization}" if self.bucket_per_org else self.s3_bucket_name

        try:
            bucket = self._s3resource.create_bucket(Bucket=bucket_name)
            bucket.wait_until_exists()
            return bucket
        except bucket.meta.client.exceptions.ClientError as error:
            logger.error("Something went wrong with creating/getting bucket %s: %s", bucket_name, error)
            raise error

    def save_raw(self, raw_id: UUID, raw: RawData) -> None:
        object_name = self._raw_file_name(raw_id, raw.boefje_meta)
        contents = self._file_middleware.encode(raw.value)

        logger.info("Writing raw data with id %s to s3", raw_id)
        bucket = self.get_or_create_bucket(raw.boefje_meta.organization)
        bucket.Object(object_name).put(Body=contents)

    def get_raw(self, raw_id: UUID, boefje_meta: BoefjeMeta) -> RawData:
        object_name = self._raw_file_name(raw_id, boefje_meta)
        bucket = self.get_or_create_bucket(boefje_meta.organization)

        try:
            contents = bucket.Object(object_name).get()["Body"].read()
        except self._s3resource.meta.client.exceptions.ClientError as error:
            if error.response["Error"]["Code"] == "404":
                raise BytesFileNotFoundException(error)
            logger.error("Could not get file from s3: %s/%s due to %s", bucket.name, object_name, error)
            raise error

        return RawData(value=self._file_middleware.decode(contents), boefje_meta=boefje_meta)

    def _raw_file_name(self, raw_id: UUID, boefje_meta: BoefjeMeta) -> str:
        if self.bucket_per_org:
            return str(raw_id)
        return f"{boefje_meta.organization}/{raw_id}"
