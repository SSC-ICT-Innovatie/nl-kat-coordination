import logging
import os
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import AmqpDsn, AnyHttpUrl, DirectoryPath, Field, FilePath, PostgresDsn
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

from bytes.models import EncryptionMiddleware, HashingAlgorithm, HashingRepositoryReference

BASE_DIR: Path = Path(__file__).parent.parent.resolve()

# Set base dir to something generic when compiling environment docs
if os.getenv("DOCS"):
    BASE_DIR = Path("../../")


class BackwardsCompatibleEnvSettings(EnvSettingsSource):
    backwards_compatibility_mapping = {
        "SECRET": "BYTES_SECRET",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "BYTES_ACCESS_TOKEN_EXPIRE_MINUTES",
        "ENCRYPTION_MIDDLEWARE": "BYTES_ENCRYPTION_MIDDLEWARE",
        "LOG_CFG": "BYTES_LOG_CFG",
        "EXT_HASH_REPOSITORY": "BYTES_EXT_HASH_REPOSITORY",
        "EXT_HASH_SERVICE": "BYTES_EXT_HASH_REPOSITORY",
        "PASTEBIN_API_DEV_KEY": "BYTES_PASTEBIN_API_DEV_KEY",
        "HASHING_ALGORITHM": "BYTES_HASHING_ALGORITHM",
        "KAT_PRIVATE_KEY_B64": "BYTES_PRIVATE_KEY_B64",
        "VWS_PUBLIC_KEY_B64": "BYTES_PUBLIC_KEY_B64",
        "RFC3161_PROVIDER": "BYTES_RFC3161_PROVIDER",
        "RFC3161_CERT_FILE": "BYTES_RFC3161_CERT_FILE",
    }

    def __call__(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        env_vars = {k.lower(): v for k, v in os.environ.items()}
        env_prefix = self.settings_cls.model_config.get("env_prefix", "").lower()

        for old_name, new_name in self.backwards_compatibility_mapping.items():
            old_name, new_name = old_name.lower(), new_name.lower()

            # New variable not explicitly set through env,
            # ...but old variable has been explicitly set through env
            if new_name not in env_vars and old_name in env_vars:
                logging.warning("Deprecation: %s is deprecated, use %s instead", old_name.upper(), new_name.upper())
                d[new_name[len(env_prefix) :]] = env_vars[old_name]

        # We previously accepted an empty value for this field
        if "rfc3161_provider" in d and not d["rfc3161_provider"]:
            del d["rfc3161_provider"]

        if "rfc3161_cert_file" in d and not d["rfc3161_cert_file"]:
            del d["rfc3161_cert_file"]

        return d


class Settings(BaseSettings):
    secret: str = Field(
        ...,
        examples=["bec4837fe5108205ce6cd1bc11735d4a220e253345e90619c6"],
        description="Secret key used for generating Bytes' API JWT",
    )
    username: str = Field(..., examples=["test"], description="Username used for generating Bytes' API JWT")
    password: str = Field(..., examples=["secret"], description="Password used for generating Bytes' API JWT")
    queue_uri: AmqpDsn = Field(..., examples=["amqp://"], description="KAT queue URI", validation_alias="QUEUE_URI")
    log_cfg: FilePath = Field(BASE_DIR / "dev.logging.conf", description="Path to the logging configuration file")

    db_uri: PostgresDsn = Field(
        ..., examples=["postgresql://xx:xx@host:5432/bytes"], description="Bytes Postgres DB URI"
    )
    data_dir: DirectoryPath = Field(
        "/data",
        description="Root for all the data. "
        "A change means that you no longer have access to old data unless you move it!",
    )

    log_file: str = Field("bytes.log", description="Optional file with Bytes logs")
    access_token_expire_minutes: float = Field(15.0, description="Access token expiration time in minutes")
    folder_permission: str = Field(
        "740", description="Unix permission level on the folders Bytes creates to save raw files"
    )
    file_permission: str = Field("640", description="Unix permission level on the raw files themselves")

    hashing_algorithm: HashingAlgorithm = Field(
        HashingAlgorithm.SHA512,
        description="Hashing algorithm used in Bytes",
        json_schema_extra={"possible_values": ["sha512", "sha224"]},
    )

    ext_hash_repository: HashingRepositoryReference = Field(
        HashingRepositoryReference.IN_MEMORY,
        description="Hashing repository used in Bytes (IN_MEMORY is a stub)",
        json_schema_extra={"possible_values": ["IN_MEMORY", "PASTEBIN", "RFC3161"]},
    )
    pastebin_api_dev_key: str | None = Field(
        None, description="API key for Pastebin. Required when using PASTEBIN hashing repository."
    )
    rfc3161_provider: AnyHttpUrl | None = Field(
        None,
        examples=["https://freetsa.org/tsr"],
        description="Timestamping. "
        "See https://github.com/trbs/rfc3161ng for a list of public providers and their certificates. "
        "Required when using RFC3161 hashing repository.",
    )
    rfc3161_cert_file: FilePath | None = Field(
        None,
        examples=["bytes/timestamping/certificates/freetsa.crt"],
        description="Path to the certificate of the RFC3161 provider. Required when using RFC3161 hashing repository. "
        "`freetsa.crt` is included in the Bytes source code.",
    )

    encryption_middleware: EncryptionMiddleware = Field(
        EncryptionMiddleware.IDENTITY,
        description="Encryption middleware used in Bytes",
        json_schema_extra={"possible_values": ["IDENTITY", "NACL_SEALBOX"]},
    )
    private_key_b64: str | None = Field(
        None,
        description="KATalogus NaCl Sealbox base-64 private key string. "
        "Required when using NACL_SEALBOX encryption middleware.",
    )
    public_key_b64: str | None = Field(
        None,
        description="KATalogus NaCl Sealbox base-64 public key string. "
        "Required when using NACL_SEALBOX encryption middleware.",
    )

    metrics_ttl_seconds: int = Field(
        300, description="The time to cache slow queries performed in the metrics endpoint"
    )
    metrics_cache_size: int = Field(
        200, description="The amount of cache entries to keep for metrics endpoints with query parameters."
    )

    span_export_grpc_endpoint: AnyHttpUrl | None = Field(
        None, description="OpenTelemetry endpoint", validation_alias="SPAN_EXPORT_GRPC_ENDPOINT"
    )

    db_connection_pool_size: int = Field(16, description="Database connection pool size")

    logging_format: Literal["text", "json"] = Field("text", description="Logging format")

    s3_bucket_prefix: str | None = Field(None, validation_alias="S3_BUCKET_PREFIX")
    s3_bucket_name: str | None = Field(None, validation_alias="S3_BUCKET")
    bucket_per_org: bool = Field(True, validation_alias="BUCKET_PER_ORG")

    model_config = SettingsConfigDict(env_prefix="BYTES_")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        backwards_compatible_settings = BackwardsCompatibleEnvSettings(settings_cls)
        return env_settings, init_settings, file_secret_settings, backwards_compatible_settings


@cache
def get_settings() -> Settings:
    return Settings()


def has_rfc3161_provider() -> bool:
    settings = get_settings()

    return bool(settings.rfc3161_provider)
