import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from catalog_starter.cache import MemoryCache
from catalog_starter.product.model import Product
from catalog_starter.product.repository import ProductStore, SqlAlchemyProductStore, UnitOfWork
from catalog_starter.product.service import ProductService
from conftest import unique


class Counter:
    by_id_calls = 0


class CountingStore(SqlAlchemyProductStore):
    def __init__(self, session: AsyncSession, counter: Counter) -> None:
        super().__init__(session)
        self.counter = counter

    async def by_id(self, product_id: uuid.UUID) -> Product:
        self.counter.by_id_calls += 1
        return await super().by_id(product_id)


class CountingUnitOfWork(UnitOfWork):
    def __init__(self, session_factory, counter: Counter) -> None:
        super().__init__(session_factory)
        self.counter = counter

    def store_of(self, session: AsyncSession) -> ProductStore:
        return CountingStore(session, self.counter)


@pytest.fixture
async def counted(stand):
    counter = Counter()
    original = stand.app.state.products
    factory = stand.app.state.session_factory
    stand.app.state.products = ProductService(lambda: CountingUnitOfWork(factory, counter), MemoryCache(600))
    yield counter
    stand.app.state.products = original


async def mouse(stand):
    return await stand.service.create(unique("Мышь для кэша"), 1990, 5)


async def test_repeated_request_is_served_from_cache(stand, counted):
    p = await mouse(stand)
    counted.by_id_calls = 0
    for _ in range(3):
        assert (await stand.client.get(f"/products/{p.id}")).status_code == 200
    assert counted.by_id_calls == 1, f"три запроса карточки должны дать одно обращение к базе, а дали {counted.by_id_calls}"


async def test_price_change_drops_the_cache(stand, counted):
    p = await mouse(stand)
    assert (await stand.client.get(f"/products/{p.id}")).json()["price"] == 1990
    res = await stand.client.patch(f"/products/{p.id}/price", json={"price": 1490.00})
    assert res.status_code == 200, res.text
    assert (await stand.client.get(f"/products/{p.id}")).json()["price"] == 1490, "после смены цены карточка должна обновиться"


async def test_reserve_drops_the_cache(stand, counted):
    p = await mouse(stand)
    assert (await stand.client.get(f"/products/{p.id}")).json()["available"] == 5
    await stand.service.reserve(p.id, 2)
    card = (await stand.client.get(f"/products/{p.id}")).json()
    assert (card["available"], card["reserved"]) == (3, 2), f"после резерва карточка должна обновиться: {card}"
