import logging.config

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import ValidationError

from bytes.api.root import router as root_router
from bytes.api.root import validation_exception_handler
from bytes.api.router import router
from bytes.config import get_settings

settings = get_settings()

logging.config.fileConfig(settings.log_cfg, disable_existing_loggers=False)
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

logger = structlog.get_logger(__name__)

app = FastAPI(title="Bytes API")

if settings.span_export_grpc_endpoint is not None:
    logger.info("Setting up instrumentation with span exporter endpoint [%s]", settings.span_export_grpc_endpoint)

    FastAPIInstrumentor.instrument_app(app)
    Psycopg2Instrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    resource = Resource(attributes={SERVICE_NAME: "bytes"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=str(settings.span_export_grpc_endpoint)))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    logger.debug("Finished setting up instrumentation")

app.include_router(root_router)
app.include_router(router, prefix="/bytes")
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
