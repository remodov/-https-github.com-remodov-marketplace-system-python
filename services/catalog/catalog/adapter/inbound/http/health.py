import asyncio
from typing import Protocol

from fastapi import APIRouter, Request, Response

from .problem import problem


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
