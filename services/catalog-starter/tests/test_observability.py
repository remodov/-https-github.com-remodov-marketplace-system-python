import httpx
import pytest
from fastapi import FastAPI, Response

from catalog_starter.observability import RequestDurationMiddleware, mount, sampler


async def database_answers() -> None:
    return None


def observed_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestDurationMiddleware, service="catalog-starter")
    mount(app, database_answers)

    @app.get("/products")
    async def products() -> Response:
        return Response(status_code=200)

    return app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=observed_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_readiness_probe_answers(client):
    res = await client.get("/health/ready")
    assert res.status_code == 204, f"проба готовности: ожидали 204, получили {res.status_code}"


async def test_liveness_probe_answers(client):
    res = await client.get("/health/live")
    assert res.status_code == 204, f"проба живости: ожидали 204, получили {res.status_code}"


async def test_prometheus_metrics_carry_service_label(client):
    await client.get("/products")
    res = await client.get("/metrics")
    assert res.status_code == 200, f"метрики: ожидали 200, получили {res.status_code}"
    for part in ("http_server_request_duration_seconds", 'service="catalog-starter"', 'route="/products"'):
        assert part in res.text, f"в метриках нет {part}"


def test_sampler_keeps_every_trace_when_ratio_is_one():
    description = sampler(1.0).get_description()
    assert "TraceIdRatioBased{1.0}" in description, f"сэмплер должен брать все трассы при доле 1.0: {description}"
