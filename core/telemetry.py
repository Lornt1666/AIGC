"""OpenTelemetry tracing and metrics setup for AIGC.

No prompt bodies, credentials, personal data, raw source code or task payloads are
recorded as telemetry attributes. Export is opt-in through OTEL_EXPORTER_OTLP_ENDPOINT.
"""
from __future__ import annotations

from contextlib import contextmanager
import logging
import os
from typing import Any, Iterator, Mapping

from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

_CONFIGURED = False
_logger = logging.getLogger("aigc.telemetry")


def configure_telemetry(service_name: str = "regenexcalibur-aigc") -> dict[str, Any]:
    global _CONFIGURED
    if _CONFIGURED:
        return {"configured": True, "already_configured": True}
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.environ.get("AIGC_BUILD_VERSION", "unversioned"),
        "deployment.environment.name": os.environ.get("AIGC_ENVIRONMENT", "local"),
    })
    tracer_provider = TracerProvider(resource=resource)
    meter_provider = MeterProvider(resource=resource)
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            # Replace the empty provider with one whose reader exports to the configured collector.
            meter_provider.shutdown()
            meter_provider = MeterProvider(resource=resource, metric_readers=[
                PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint), export_interval_millis=15000)
            ])
        except Exception as exc:
            _logger.error("telemetry_exporter_configuration_failed", extra={"error_type": type(exc).__name__})
            return {"configured": False, "reason": "exporter_configuration_failed"}
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)
    _CONFIGURED = True
    return {"configured": True, "export_enabled": bool(endpoint)}


@contextmanager
def traced_operation(name: str, attributes: Mapping[str, str | int | bool] | None = None) -> Iterator[Any]:
    tracer = trace.get_tracer("regenexcalibur.aigc")
    with tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            if key.lower() in {"token", "authorization", "prompt", "source", "payload", "email", "secret"}:
                continue
            if isinstance(value, (str, int, bool)):
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.set_attribute("error.type", type(exc).__name__)
            span.set_status(__import__("opentelemetry.trace", fromlist=["Status"]).Status(
                __import__("opentelemetry.trace", fromlist=["StatusCode"]).StatusCode.ERROR))
            raise
