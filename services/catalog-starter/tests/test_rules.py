from decimal import Decimal

import pytest

from catalog_starter.product.errors import InvalidError, OutOfStockError
from catalog_starter.product.model import MAX_DISCOUNT_PERCENT, Product


def product(price: str, stock: int) -> Product:
    return Product.create("Товар", Decimal(price), stock)


@pytest.mark.parametrize("price", ["0", "-1"])
def test_price_must_be_positive(price):
    with pytest.raises(InvalidError):
        product(price, 1)


@pytest.mark.parametrize("percent", [0, -5, MAX_DISCOUNT_PERCENT + 1, 100])
def test_discount_outside_range_is_rejected_and_keeps_price(percent):
    p = product("1000.00", 1)
    with pytest.raises(InvalidError):
        p.apply_discount(percent)
    assert p.price == Decimal("1000.00"), f"неудачная скидка изменила цену: {p.price}"


def test_discount_at_the_limit_is_allowed():
    p = product("1000.00", 1)
    p.apply_discount(MAX_DISCOUNT_PERCENT)
    assert p.price == Decimal("500")


def test_discount_is_rounded_to_kopecks():
    p = product("999.99", 1)
    p.apply_discount(33)
    assert str(p.price) == "669.99", f"33% от 999.99 это 669.9933, ждём 669.99, получили {p.price}"


def test_zero_stock_change_is_rejected():
    with pytest.raises(InvalidError):
        product("10.00", 3).change_stock(0)


def test_write_off_below_zero_is_rejected():
    p = product("10.00", 3)
    with pytest.raises(OutOfStockError):
        p.change_stock(-4)
    assert p.stock == 3, "остаток после отказа не должен меняться"


def test_reserve_more_than_available_is_rejected():
    p = product("10.00", 3)
    with pytest.raises(OutOfStockError) as caught:
        p.reserve(4)
    assert (caught.value.requested, caught.value.available) == (4, 3)


def test_state_is_changed_only_through_methods():
    p = product("10.00", 1)
    with pytest.raises(AttributeError):
        p.price = Decimal("1.00")  # type: ignore[misc]
    with pytest.raises(AttributeError):
        p.stock = 100  # type: ignore[misc]
    public = [name for name in Product.__mapper__.column_attrs.keys() if not name.startswith("_")]
    assert public == [], f"колонки {public} открыты: правило можно обойти, присвоив поле напрямую"
