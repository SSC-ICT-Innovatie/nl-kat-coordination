from typing import Any

import fastapi
import prometheus_client
import structlog
from fastapi import status
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from scheduler import context


class MetricsAPI:
    def __init__(self, api: fastapi.FastAPI, ctx: context.AppContext) -> None:
        self.logger: structlog.BoundLogger = structlog.getLogger(__name__)
        self.api = api
        self.ctx = ctx

        # Set up OpenTelemetry instrumentation
        if self.ctx.config.host_metrics is not None:
            self.logger.info(
                "Setting up instrumentation with span exporter endpoint [%s]", self.ctx.config.host_metrics
            )

            FastAPIInstrumentor.instrument_app(self.api)
            Psycopg2Instrumentor().instrument()
            HTTPXClientInstrumentor().instrument()

            resource = Resource(attributes={SERVICE_NAME: "mula"})
            provider = TracerProvider(resource=resource)
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=str(self.ctx.config.host_metrics)))
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)

            self.logger.debug("Finished setting up OpenTelemetry instrumentation")

        self.api.add_api_route(
            path="/metrics",
            endpoint=self.metrics,
            methods=["GET"],
            status_code=status.HTTP_200_OK,
            description="OpenMetrics compliant metrics endpoint",
        )

    def metrics(self) -> Any:
        data = prometheus_client.generate_latest(self.ctx.metrics_registry)
        response = fastapi.Response(media_type="text/plain", content=data)
        return response
