import logging
import socket
from contextlib import asynccontextmanager
from logging import config
from pathlib import Path

import structlog
import yaml
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from httpx import RequestError
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pika.adapters.utils.connection_workflow import AMQPConnectionWorkflowFailed

from octopoes.api.bulk_router import router as bulk_router
from octopoes.api.models import ServiceHealth
from octopoes.api.router import router
from octopoes.config.settings import Settings
from octopoes.core.app import close_rabbit_channel
from octopoes.events.manager import get_rabbit_channel
from octopoes.models.exception import ObjectNotFoundException, TypeNotFound
from octopoes.version import __version__
from octopoes.xtdb.exceptions import NodeNotFound
from octopoes.xtdb.query import InvalidField, InvalidPath

settings = Settings()
logger = logging.getLogger(__name__)

# Load log config
try:
    with Path(settings.log_cfg).open() as log_config:
        config.dictConfig(yaml.safe_load(log_config))
        logger.info("Configured loggers with config: %s", settings.log_cfg)
except FileNotFoundError:
    logger.warning("No log config found at: %s", settings.log_cfg)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper("iso", utc=False),
        (
            structlog.dev.ConsoleRenderer(
                colors=True, pad_level=False, exception_formatter=structlog.dev.plain_traceback
            )
            if settings.logging_format == "text"
            else structlog.processors.JSONRenderer()
        ),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_rabbit_channel(str(settings.queue_uri))
    except (AMQPConnectionWorkflowFailed, socket.gaierror):
        logger.exception("Unable to connect RabbitMQ on startup")
    yield
    # clean up items
    close_rabbit_channel(str(settings.queue_uri))


app = FastAPI(title="Octopoes API", lifespan=lifespan)

# Set up OpenTelemetry instrumentation
if settings.span_export_grpc_endpoint is not None:
    logger.info("Setting up instrumentation with span exporter endpoint [%s]", settings.span_export_grpc_endpoint)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()

    resource = Resource(attributes={SERVICE_NAME: "octopoes"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=str(settings.span_export_grpc_endpoint)))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    logger.debug("Finished setting up instrumentation")


@app.exception_handler(RequestValidationError)
def http_validation_exception_handler(_: Request, exc: RequestValidationError) -> None:
    logger.info(exc)
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@app.exception_handler(RequestError)
def http_exception_handler(_: Request, exc: RequestError) -> None:
    logger.error(exc)
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.exception_handler(InvalidField)
def invalid_field(_: Request, exc: InvalidField) -> None:
    logger.info(exc)
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.exception_handler(InvalidPath)
def invalid_path(_: Request, exc: InvalidPath) -> None:
    logger.info(exc)
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.exception_handler(ValueError)
def value_error(_: Request, exc: ValueError) -> None:
    logger.info(exc)
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.exception_handler(TypeNotFound)
def type_not_found(_: Request, exc: TypeNotFound) -> None:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Type not found")


@app.exception_handler(NodeNotFound)
def node_not_found_exception_handler(_: Request, exc: NodeNotFound) -> None:
    logger.info(exc)
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Node not found")


@app.exception_handler(ObjectNotFoundException)
def not_found_exception_handler(_: Request, exc: ObjectNotFoundException) -> None:
    logger.info(exc)
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.exception_handler(Exception)
def uncaught_exception_handler(_: Request, exc: Exception) -> None:
    logger.error(exc)
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exc.__class__.__name__}: {exc}")


@app.get("/health")
def root_health() -> ServiceHealth:
    return ServiceHealth(service="octopoes", healthy=True, version=__version__)


app.include_router(router)
app.include_router(bulk_router)
