import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Protocol

from fastapi import APIRouter, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from .inbox import Notification, Processor


class Pinger(Protocol):
    async def ping(self) -> None: ...


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True)


class NotificationResponse(ApiModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_type: str
    user_id: uuid.UUID
    channel: str
    template_key: str
    status: str
    created_at: datetime


class NotificationList(ApiModel):
    items: list[NotificationResponse]


def health_router(database: Pinger) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health/live", status_code=204)
    async def live() -> Response:
        return Response(status_code=204)

    @router.get("/health/ready", status_code=204)
    async def ready() -> Response:
        try:
            async with asyncio.timeout(2):
                await database.ping()
        except Exception:
            return JSONResponse({"code": "NOT_READY", "detail": "База недоступна"}, status_code=503)
        return Response(status_code=204)

    return router


def notification_router(processor: Processor, admin_token: str) -> APIRouter:
    router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

    @router.get("", response_model=NotificationList)
    async def list_notifications(
        user_id: Annotated[uuid.UUID, Query(alias="userId")],
        authorization: Annotated[str, Header()] = "",
    ):
        if authorization.removeprefix("Bearer ") != admin_token:
            return JSONResponse({"code": "ACCESS_DENIED"}, status_code=403)
        items = await processor.list_by_user(user_id)
        return NotificationList(items=[response_of(item) for item in items])

    return router


def response_of(item: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=item.id,
        event_id=item.event_id,
        event_type=item.event_type,
        user_id=item.user_id,
        channel=item.channel,
        template_key=item.template_key,
        status=item.status,
        created_at=item.created_at,
    )


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"code": "VALIDATION_ERROR", "detail": "userId должен быть UUID"}, status_code=400
        )
