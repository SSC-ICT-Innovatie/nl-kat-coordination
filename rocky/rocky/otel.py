import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = structlog.get_logger(__name__)


class OpenTelemetryHelper:
    """
    Helper class to set up OpenTelemetry instrumentation.
    """

    @staticmethod
    def setup_instrumentation(span_export_grpc_endpoint):
        logger.info("Setting up instrumentation with span exporter endpoint [%s]", span_export_grpc_endpoint)

        DjangoInstrumentor().instrument(is_sql_commentor_enabled=True)
        Psycopg2Instrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        resource = Resource(attributes={SERVICE_NAME: "rocky"})
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=span_export_grpc_endpoint))
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        logger.debug("Finished setting up instrumentation")
