import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import AnyHttpUrl, Field, FilePath, IPvAnyAddress, PostgresDsn, conint
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import EnvSettingsSource

BASE_DIR: Path = Path(__file__).parent.resolve()

# Set base dir to something generic when compiling environment docs
if os.getenv("DOCS"):
    BASE_DIR = Path("../")


class EncryptionMiddleware(Enum):
    IDENTITY = "IDENTITY"
    NACL_SEALBOX = "NACL_SEALBOX"


class BackwardsCompatibleEnvSettings(EnvSettingsSource):
    backwards_compatibility_mapping = {
        "BOEFJES_BOEFJE_API_HOST": "BOEFJES_API_HOST",
        "BOEFJES_BOEFJE_API_PORT": "BOEFJES_API_PORT",
        "BOEFJE_API": "BOEFJES_API",
        "BOEFJE_DOCKER_NETWORK": "BOEFJES_DOCKER_NETWORK",
        "LOG_CFG": "BOEFJES_LOG_CFG",
        "ENCRYPTION_MIDDLEWARE": "BOEFJES_ENCRYPTION_MIDDLEWARE",
        "KATALOGUS_PRIVATE_KEY_B64": "BOEFJES_KATALOGUS_PRIVATE_KEY",
        "KATALOGUS_PUBLIC_KEY_B64": "BOEFJES_KATALOGUS_PUBLIC_KEY",
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

        return d


class Settings(BaseSettings):
    log_cfg: FilePath = Field(BASE_DIR / "logging.json", description="Path to the logging configuration file")

    # Worker configuration
    pool_size: int = Field(2, description="Number of workers to run per queue")
    poll_interval: float = Field(10.0, description="Time to wait before polling for tasks when all queues are empty")
    worker_heartbeat: float = Field(1.0, description="Seconds to wait before checking the workers when queues are full")
    deduplicate: bool = Field(False, description="Whether to apply deduplication")
    plugins: list[str] = Field(
        default_factory=list, description="A list of plugin ids to filter on.", examples=['["dns-records"]']
    )
    images: list[str] = Field(
        default_factory=list,
        description="A list of oci images to filter on.",
        examples=['["ghcr.io/minvws/openkat/generic:latest"]'],
    )

    remote_ns: IPvAnyAddress = Field(
        "1.1.1.1", description="Name server used for remote DNS resolution in the boefje runner"
    )

    scan_profile_whitelist: dict[str, conint(strict=True, ge=0, le=4)] = Field(  # type: ignore
        default_factory=dict,
        description="Whitelist for normalizer ids allowed to produce scan profiles, including a maximum level.",
        examples=['{"kat_external_db_normalize": 3, "kat_dns_normalize": 1}'],
    )

    katalogus_db_uri: PostgresDsn = Field(
        ...,
        examples=["postgresql://xx:xx@host:5432/katalogus"],
        description="Katalogus Postgres DB URI",
        validation_alias="KATALOGUS_DB_URI",
    )

    db_connection_pool_size: int = Field(
        16, description="Database connection pool size", validation_alias="KATALOGUS_DB_CONNECTION_POOL_SIZE"
    )

    scheduler_api: AnyHttpUrl = Field(
        ..., examples=["http://localhost:8004"], description="Mula API URL", validation_alias="SCHEDULER_API"
    )
    katalogus_api: AnyHttpUrl = Field(
        ..., examples=["http://localhost:8003"], description="Katalogus API URL", validation_alias="KATALOGUS_API"
    )
    octopoes_api: AnyHttpUrl = Field(
        ..., examples=["http://localhost:8001"], description="Octopoes API URL", validation_alias="OCTOPOES_API"
    )
    api: AnyHttpUrl = Field(
        ..., examples=["http://boefje:8000"], description="The URL on which the boefjes API is available"
    )
    # Boefje server settings
    api_host: str = Field("0.0.0.0", description="Host address of the Boefje API server")
    api_port: int = Field(8000, description="Host port of the Boefje API server")
    docker_network: str = Field("bridge", description="Docker network to run Boefjes in")
    bytes_api: AnyHttpUrl = Field(
        ..., examples=["http://localhost:8002"], description="Bytes API URL", validation_alias="BYTES_API"
    )
    bytes_username: str = Field(
        ..., examples=["test"], description="Bytes JWT login username", validation_alias="BYTES_USERNAME"
    )
    bytes_password: str = Field(
        ..., examples=["secret"], description="Bytes JWT login password", validation_alias="BYTES_PASSWORD"
    )

    encryption_middleware: EncryptionMiddleware = Field(
        EncryptionMiddleware.IDENTITY,
        description="Toggle used to configure the encryption strategy",
        examples=["IDENTITY", "NACL_SEALBOX"],
    )

    katalogus_private_key: str = Field(
        "", description="Base64 encoded private key used for asymmetric encryption of settings"
    )
    katalogus_public_key: str = Field(
        "", description="Base64 encoded public key used for asymmetric encryption of settings"
    )

    span_export_grpc_endpoint: AnyHttpUrl | None = Field(
        None, description="OpenTelemetry endpoint", validation_alias="SPAN_EXPORT_GRPC_ENDPOINT"
    )

    logging_format: Literal["text", "json"] = Field("text", description="Logging format")

    outgoing_request_timeout: int = Field(30, description="Timeout for outgoing HTTP requests")

    model_config = SettingsConfigDict(env_prefix="BOEFJES_")

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


# Do not initialize the settings module when compiling environment docs
if not os.getenv("DOCS"):
    settings = Settings()
