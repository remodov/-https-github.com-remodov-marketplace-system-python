import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..adapter.inbound.http.health import health_router
from ..adapter.inbound.http.problem import install_handlers
from ..adapter.inbound.http.products import product_router
from ..adapter.outbound.persistence.engine import (
    DatabasePinger,
    make_engine,
    make_session_factory,
    run_migrations,
)
from .config import Settings
from .wire import Deps, authenticator_of, wire_handlers

log = logging.getLogger("catalog")


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    settings = settings or Settings()
    deps = deps or Deps()
    engine = make_engine(settings.database_url)
    handlers = wire_handlers(make_session_factory(engine), deps)
    auth = authenticator_of(settings, deps)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_migrations(engine)
        log.info("каталог готов, порт %s, аутентификация %s", settings.http_port, settings.auth_mode)
        yield
        await engine.dispose()

    app = FastAPI(title="Каталог", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    install_handlers(app)
    app.include_router(health_router(DatabasePinger(engine)))
    app.include_router(
        product_router(auth, handlers.create, handlers.price, handlers.transitions, handlers.queries)
    )
    return app
