import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from .cache import Cache, MemoryCache, RedisCache
from .config import Settings
from .db import make_engine, make_session_factory, run_migrations
from .observability import RequestDurationMiddleware, mount, tracing
from .problem import install_handlers
from .product.repository import UnitOfWork
from .product.router import router as products
from .product.service import ProductService

log = logging.getLogger("catalog")


def cache_of(settings: Settings) -> Cache:
    if settings.cache == "memory":
        return MemoryCache(settings.cache_ttl_seconds)
    return RedisCache(settings.redis_url, settings.cache_ttl_seconds)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        await run_migrations(engine)
        session_factory = make_session_factory(engine)
        cache = cache_of(settings)
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.cache = cache
        app.state.products = ProductService(lambda: UnitOfWork(session_factory), cache)
        log.info("каталог готов, порт %s", settings.http_port)
        yield
        if isinstance(cache, RedisCache):
            await cache.close()
        await engine.dispose()
        if app.state.tracer_provider is not None:
            app.state.tracer_provider.shutdown()

    app = FastAPI(title="Каталог: учебная версия", lifespan=lifespan)
    app.state.settings = settings

    async def database_answers() -> None:
        async with app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    app.add_middleware(RequestDurationMiddleware, service=settings.service_name)
    install_handlers(app)
    mount(app, database_answers)
    app.include_router(products)
    app.state.tracer_provider = tracing(app, settings)
    return app


app = create_app()
