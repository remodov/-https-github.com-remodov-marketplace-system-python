import asyncio

from conftest import unique

BUYERS = 100
STOCK = 10


async def test_hundred_buyers_sell_exactly_the_stock(stand):
    p = await stand.must_create(unique("Билет на распродажу"), "100.00", STOCK)

    outcomes = await asyncio.gather(
        *(stand.service.reserve(p.id, 1) for _ in range(BUYERS)), return_exceptions=True
    )
    sold = sum(1 for outcome in outcomes if not isinstance(outcome, BaseException))

    after = await stand.service.by_id(p.id)
    assert sold == STOCK, f"успешных резервов {sold}, а товара было {STOCK}"
    assert (after.reserved, after.available) == (STOCK, 0), f"после распродажи reserved={after.reserved} available={after.available}"
    assert after.stock == STOCK, f"остаток на складе резерв не трогает, а он стал {after.stock}"
