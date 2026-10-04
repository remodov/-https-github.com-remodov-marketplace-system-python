import asyncio
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, Sampler, TraceIdRatioBased
from prometheus_client import CONTENT_TYPE_LATEST, Histogram, generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings

ReadyCheck = Callable[[], Awaitable[None]]

READY_TIMEOUT_SECONDS = 2
PROBLEM = "application/problem+json"

request_duration = Histogram(
    "http_server_request_duration_seconds",
    "Время ответа HTTP по маршрутам",
    ["service", "method", "route", "status"],
)


def mount(app: FastAPI, ready: ReadyCheck) -> None:
    @app.get("/health/live", status_code=204)
    async def live() -> Response:
        return Response(status_code=204)

    @app.get("/health/ready", status_code=204)
    async def ready_for_traffic(request: Request) -> Response:
        try:
            async with asyncio.timeout(READY_TIMEOUT_SECONDS):
                await ready()
        except Exception:
            return not_ready(request.url.path)
        return Response(status_code=204)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def not_ready(instance: str) -> JSONResponse:
    body = {
        "type": "about:blank",
        "title": "Service Unavailable",
        "status": 503,
        "code": "NOT_READY",
        "detail": "База недоступна",
        "instance": instance,
    }
    return JSONResponse(body, status_code=503, media_type=PROBLEM)


class RequestDurationMiddleware:
    def __init__(self, app: ASGIApp, service: str) -> None:
        self.app = app
        self.service = service

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def remember_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, remember_status)
        finally:
            labels = (self.service, scope["method"], route_template(scope), str(status))
            request_duration.labels(*labels).observe(time.perf_counter() - started)


def route_template(scope: Scope) -> str:
    route = scope.get("route")
    return route.path if route is not None else "unmatched"


def sampler(ratio: float) -> Sampler:
    return ParentBased(TraceIdRatioBased(ratio))


def tracing(app: FastAPI, settings: Settings) -> TracerProvider | None:
    if not settings.otel_exporter_otlp_endpoint:
        return None
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: settings.service_name}),
        sampler=sampler(settings.trace_sample_ratio),
    )
    traces_url = f"{settings.otel_exporter_otlp_endpoint.rstrip('/')}/v1/traces"
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_url)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    return provider
