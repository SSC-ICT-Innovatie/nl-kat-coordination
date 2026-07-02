from typing import Any

import prometheus_client
import structlog
from fastapi import APIRouter, Depends, status
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, ValidationError

from bytes.api.metrics import get_registry
from bytes.auth import TokenResponse, authenticate_token, get_access_token
from bytes.database.sql_meta_repository import create_meta_data_repository
from bytes.repositories.meta_repository import MetaDataRepository
from bytes.version import __version__

router = APIRouter()
logger = structlog.get_logger(__name__)


class ServiceHealth(BaseModel):
    service: str
    healthy: bool = False
    version: str | None = None
    additional: Any = None
    results: list["ServiceHealth"] = Field(default_factory=list)


ServiceHealth.model_rebuild()


def validation_exception_handler(_: Request, exc: RequestValidationError | ValidationError) -> JSONResponse:
    logger.critical(exc)
    return JSONResponse({"value": str(exc)}, status.HTTP_422_UNPROCESSABLE_ENTITY)


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/health")


@router.get("/health", response_model=ServiceHealth)
def health() -> ServiceHealth:
    bytes_health = ServiceHealth(service="bytes", healthy=True, version=__version__)
    return bytes_health


@router.get("/metrics", dependencies=[Depends(authenticate_token)])
def metrics(meta_repository: MetaDataRepository = Depends(create_meta_data_repository)) -> Response:
    collector_registry = get_registry(meta_repository)
    data = prometheus_client.generate_latest(collector_registry)

    return Response(media_type="text/plain", content=data)


@router.post("/token", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    access_token, expire_time = get_access_token(form_data)

    return TokenResponse(access_token=access_token, token_type="bearer", expires_at=expire_time.isoformat())
