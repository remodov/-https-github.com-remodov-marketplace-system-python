import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

import httpx

from ....core.errors import not_found
from ....core.order.aggregate.order import Money


@dataclass(frozen=True)
class CatalogSettings:
    base_url: str
    connect_timeout: float
    request_timeout: float
    attempts: int
    backoff: float
    breaker_failures: int
    breaker_open_for: float


class UnexpectedAnswer(Exception):
    pass


class CatalogClient:
    # TODO шаг 8: таймауты на соединение и чтение через httpx.Timeout и размыкатель
    # CircuitBreaker из breaker.py с порогом из настроек; товар, которого нет,
    # размыкатель за отказ считать не должен.
    def __init__(self, settings: CatalogSettings) -> None:
        self.settings = settings
        self.http = httpx.AsyncClient(base_url=settings.base_url)

    # TODO шаг 8: обход товаров под размыкателем; открытый размыкатель и исчерпанные
    # попытки уходят наружу как SERVICE_DEGRADED, а не как ошибка клиента.
    async def prices(self, product_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Money]:
        return {product_id: await self._fetch_once(product_id) for product_id in product_ids}

    async def aclose(self) -> None:
        await self.http.aclose()

    # TODO шаг 8: повтор с паузой; повторять только сетевые ошибки (httpx.TransportError)
    # и 5xx, 404 оставлять PRODUCT_NOT_FOUND без повтора.
    async def _fetch_once(self, product_id: uuid.UUID) -> Money:
        response = await self.http.get(f"/api/v1/products/{product_id}")
        if response.status_code == 404:
            raise not_found("PRODUCT_NOT_FOUND", f"Товар {product_id} не найден в каталоге")
        if response.status_code != 200:
            raise UnexpectedAnswer(f"каталог ответил {response.status_code}")
        body = json.loads(response.content, parse_float=Decimal)
        return Money(Decimal(body["price"]), body["currency"])
