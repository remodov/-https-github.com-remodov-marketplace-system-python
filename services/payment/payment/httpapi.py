import asyncio
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Protocol

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel

from .model import InvalidTransition, Payment, PaymentNotFound
from .service import Service

log = logging.getLogger("payment.http")

PROBLEM = "application/problem+json"


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True)


class AuthorizeRequest(ApiModel):
    order_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)


class PaymentResponse(ApiModel):
    id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    updated_at: datetime

    @field_serializer("amount")
    def amount_as_number(self, value: Decimal) -> float:
        return float(value)


def response_of(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        order_id=payment.order_id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status.value,
        updated_at=payment.updated_at.astimezone(UTC),
    )


def payment_router(service: Service) -> APIRouter:
    router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

    @router.post("", status_code=201)
    async def authorize(body: AuthorizeRequest) -> PaymentResponse:
        return response_of(await service.authorize(body.order_id, body.amount, body.currency))

    @router.get("/{payment_id}")
    async def by_id(payment_id: uuid.UUID) -> PaymentResponse:
        return response_of(await service.by_id(payment_id))

    @router.post("/{payment_id}/capture")
    async def capture(payment_id: uuid.UUID) -> PaymentResponse:
        return response_of(await service.capture(payment_id))

    @router.post("/{payment_id}/refund")
    async def refund(payment_id: uuid.UUID) -> PaymentResponse:
        return response_of(await service.refund(payment_id))

    return router


class Pinger(Protocol):
    async def ping(self) -> None: ...


def health_router(database: Pinger) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health/live", status_code=204)
    async def live() -> Response:
        return Response(status_code=204)

    @router.get("/health/ready", status_code=204)
    async def ready(request: Request) -> Response:
        try:
            async with asyncio.timeout(2):
                await database.ping()
        except Exception:
            return problem(503, "NOT_READY", "База недоступна", request.url.path)
        return Response(status_code=204)

    return router


def problem(status: int, code: str, detail: str, instance: str) -> JSONResponse:
    body = {
        "type": f"urn:problem:payment:{code}",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM)


def is_unreadable_body(error: dict) -> bool:
    return error.get("type") == "json_invalid" or tuple(error.get("loc", ())) == ("body",)


def is_path_parameter(error: dict) -> bool:
    return tuple(error.get("loc", ()))[:1] == ("path",)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(PaymentNotFound)
    async def on_not_found(request: Request, exc: PaymentNotFound) -> JSONResponse:
        return problem(404, "PAYMENT_NOT_FOUND", "Платёж не найден", request.url.path)

    @app.exception_handler(InvalidTransition)
    async def on_invalid_transition(request: Request, exc: InvalidTransition) -> JSONResponse:
        return problem(409, "INVALID_PAYMENT_TRANSITION", str(exc), request.url.path)

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        if any(is_unreadable_body(error) for error in errors):
            return problem(400, "MALFORMED_REQUEST", "Невозможно разобрать тело запроса", request.url.path)
        if any(is_path_parameter(error) for error in errors):
            return problem(
                400, "VALIDATION_ERROR", "Идентификатор платежа должен быть UUID", request.url.path
            )
        return problem(
            400,
            "VALIDATION_ERROR",
            "Нужны orderId, сумма больше нуля и валюта из трёх букв",
            request.url.path,
        )

    @app.exception_handler(Exception)
    async def on_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("необработанная ошибка на %s", request.url.path)
        return problem(500, "INTERNAL_SERVER_ERROR", "Внутренняя ошибка сервиса", request.url.path)
