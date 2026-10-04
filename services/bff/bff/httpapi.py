import logging
import uuid

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import DownstreamError, ScreenNotAssembled
from .problem import problem
from .screen import OrderScreen, ScreenAssembler

log = logging.getLogger("bff.http")


def screen_router(screens: ScreenAssembler) -> APIRouter:
    router = APIRouter(prefix="/api/v1/screens", tags=["screens"])

    @router.get("/order/{order_id}")
    async def order_screen(order_id: uuid.UUID, request: Request) -> OrderScreen:
        return await screens.assemble(order_id, request.headers.get("Authorization", ""))

    return router


def health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health/live", status_code=204)
    async def live() -> Response:
        return Response(status_code=204)

    @router.get("/health/ready", status_code=204)
    async def ready() -> Response:
        return Response(status_code=204)

    return router


def not_assembled(error: ScreenNotAssembled, instance: str) -> JSONResponse:
    if isinstance(error, DownstreamError) and error.service == "order":
        if error.status == 404:
            return problem(404, "ORDER_NOT_FOUND", "Заказ не найден", instance)
        if error.status in (401, 403):
            return problem(
                error.status, "ORDER_ACCESS_DENIED", "Заказ недоступен этому пользователю", instance
            )
    log.warning("экран заказа не собран: %s", error)
    return problem(
        502, "DOWNSTREAM_UNAVAILABLE", "Сервис-источник не ответил, экран собрать не удалось", instance
    )


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ScreenNotAssembled)
    async def on_not_assembled(request: Request, exc: ScreenNotAssembled) -> JSONResponse:
        return not_assembled(exc, request.url.path)

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem(400, "VALIDATION_ERROR", "orderId должен быть UUID", request.url.path)

    @app.exception_handler(Exception)
    async def on_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("необработанная ошибка на %s", request.url.path)
        return problem(500, "INTERNAL_SERVER_ERROR", "Внутренняя ошибка сервиса", request.url.path)
