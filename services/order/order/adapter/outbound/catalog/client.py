import asyncio
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

import httpx

from ....core.errors import AppError, Kind, not_found, unavailable
from ....core.order.aggregate.order import Money
from .breaker import CircuitBreaker, CircuitOpen


@dataclass(frozen=True)
class CatalogSettings:
    base_url: str
    connect_timeout: float
    request_timeout: float
    attempts: int
    backoff: float
    breaker_failures: int
    breaker_open_for: float


class TransientFailure(Exception):
    pass


class UnexpectedAnswer(Exception):
    pass


class CatalogClient:
    def __init__(self, settings: CatalogSettings) -> None:
        self.settings = settings
        self.http = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=httpx.Timeout(
                connect=settings.connect_timeout,
                read=settings.request_timeout,
                write=settings.request_timeout,
                pool=settings.connect_timeout,
            ),
        )
        self.breaker = CircuitBreaker(settings.breaker_failures, settings.breaker_open_for)

    async def prices(self, product_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Money]:
        if not self.breaker.allows_call():
            raise degraded() from CircuitOpen("размыкатель каталога открыт")
        try:
            prices = {product_id: await self._fetch_with_retry(product_id) for product_id in product_ids}
        except AppError as error:
            if error.kind is Kind.NOT_FOUND:
                self.breaker.succeeded()
            else:
                self.breaker.failed()
            raise
        except BaseException:
            self.breaker.failed()
            raise
        self.breaker.succeeded()
        return prices

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _fetch_with_retry(self, product_id: uuid.UUID) -> Money:
        last_failure: TransientFailure | None = None
        for attempt in range(1, max(self.settings.attempts, 1) + 1):
            if last_failure is not None:
                await asyncio.sleep(self.settings.backoff * (attempt - 1))
            try:
                return await self._fetch_once(product_id)
            except TransientFailure as failure:
                last_failure = failure
        raise degraded() from last_failure

    async def _fetch_once(self, product_id: uuid.UUID) -> Money:
        try:
            response = await self.http.get(f"/api/v1/products/{product_id}")
        except httpx.TransportError as error:
            raise TransientFailure(str(error)) from error
        if response.status_code == 404:
            raise not_found("PRODUCT_NOT_FOUND", f"Товар {product_id} не найден в каталоге")
        if response.status_code >= 500:
            raise TransientFailure(f"каталог ответил {response.status_code}")
        if response.status_code != 200:
            raise degraded() from UnexpectedAnswer(f"каталог ответил {response.status_code}")
        try:
            body = json.loads(response.content, parse_float=Decimal)
            return Money(Decimal(body["price"]), body["currency"])
        except (ValueError, KeyError, TypeError) as error:
            raise degraded() from error


def degraded() -> AppError:
    return unavailable("SERVICE_DEGRADED", "Каталог временно недоступен")
