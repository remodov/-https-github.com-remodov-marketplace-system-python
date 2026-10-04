import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from .config import Settings
from .httpapi import health_router, install_handlers, screen_router
from .ratelimit import Limiter, RateLimitMiddleware
from .screen import ScreenAssembler

log = logging.getLogger("bff")

REDIS_TIMEOUT_SECONDS = 1.0


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    redis = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
    )
    limiter = Limiter(redis, settings.rate_limit_per_minute)
    screens = ScreenAssembler.for_urls(settings.order_url, settings.catalog_url, settings.payment_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("bff готов, порт %s", settings.http_port)
        yield
        await screens.aclose()
        await redis.aclose()

    app = FastAPI(title="BFF", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    install_handlers(app)
    app.include_router(health_router())
    app.include_router(screen_router(screens))
    return app
