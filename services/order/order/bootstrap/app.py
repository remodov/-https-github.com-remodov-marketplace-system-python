import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..adapter.inbound.http.health import health_router
from ..adapter.inbound.http.orders import order_router
from ..adapter.inbound.http.problem import install_handlers
from ..adapter.outbound.catalog.client import CatalogClient
from ..adapter.outbound.persistence.engine import (
    DatabasePinger,
    make_engine,
    make_session_factory,
    run_migrations,
)
from .config import Settings
from .wire import Deps, authenticator_of, catalog_of, wire_handlers

log = logging.getLogger("order")


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    settings = settings or Settings()
    deps = deps or Deps()
    engine = make_engine(settings.database_url)
    catalog = catalog_of(settings, deps)
    handlers = wire_handlers(make_session_factory(engine), catalog, deps)
    auth = authenticator_of(settings, deps)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_migrations(engine)
        log.info(
            "сервис заказов готов, порт %s, каталог %s, аутентификация %s",
            settings.http_port,
            settings.catalog_url,
            settings.auth_mode,
        )
        yield
        await engine.dispose()
        if isinstance(catalog, CatalogClient):
            await catalog.aclose()

    app = FastAPI(title="Заказы", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    install_handlers(app)
    app.include_router(health_router(DatabasePinger(engine)))
    app.include_router(order_router(auth, handlers.create, handlers.queries))
    return app
