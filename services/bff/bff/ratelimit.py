import logging
import time
from dataclasses import dataclass

from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .problem import problem

log = logging.getLogger("bff.ratelimit")

WINDOW_SECONDS = 60
CLIENT_HEADER = "X-Client-Id"
ANONYMOUS = "anonymous"
REMAINING_HEADER = "X-RateLimit-Remaining"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    remaining: int
    retry_after: int


class Limiter:
    def __init__(self, redis: Redis, per_minute: int) -> None:
        self.redis = redis
        self.per_minute = per_minute

    async def check(self, client: str) -> Decision:
        key = f"rate:{client}:{int(time.time() // WINDOW_SECONDS)}"
        used = await self.redis.incr(key)
        if used == 1:
            await self.redis.expire(key, WINDOW_SECONDS)
        return Decision(
            allowed=used <= self.per_minute,
            remaining=max(self.per_minute - used, 0),
            retry_after=WINDOW_SECONDS,
        )


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, limiter: Limiter, protected_prefix: str = "/api/") -> None:
        self.app = app
        self.limiter = limiter
        self.protected_prefix = protected_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.protected_prefix):
            await self.app(scope, receive, send)
            return
        client = Headers(scope=scope).get(CLIENT_HEADER, "").strip() or ANONYMOUS
        try:
            decision = await self.limiter.check(client)
        except RedisError as error:
            log.warning("лимит частоты не проверен, запрос пропущен: client=%s err=%s", client, error)
            await self.app(scope, receive, send)
            return
        if not decision.allowed:
            await rejected(decision, scope["path"])(scope, receive, send)
            return

        async def send_with_remaining(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REMAINING_HEADER] = str(decision.remaining)
            await send(message)

        await self.app(scope, receive, send_with_remaining)


def rejected(decision: Decision, path: str) -> JSONResponse:
    response = problem(429, "RATE_LIMITED", "Слишком много запросов, попробуйте позже", path)
    response.headers["Retry-After"] = str(decision.retry_after)
    response.headers[REMAINING_HEADER] = str(decision.remaining)
    return response
