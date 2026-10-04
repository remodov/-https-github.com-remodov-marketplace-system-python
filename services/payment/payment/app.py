import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from .config import Settings
from .httpapi import health_router, install_handlers, payment_router
from .repository import Database
from .service import Clock, Service

log = logging.getLogger("payment")


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or Settings()
    database = Database(settings.database_url)
    service = Service(database, clock or SystemClock())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await database.start()
        log.info("сервис платежей готов, порт %s", settings.http_port)
        yield
        await database.aclose()

    app = FastAPI(title="Платежи", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    install_handlers(app)
    app.include_router(health_router(database))
    app.include_router(payment_router(service))
    return app
