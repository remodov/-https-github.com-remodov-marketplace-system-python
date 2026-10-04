import uuid

from conftest import unique


async def mouse(stand):
    return await stand.must_create(unique("Беспроводная мышь"), "1990.00", 5)


async def test_price_is_changed(stand):
    p = await mouse(stand)
    res = await stand.client.patch(f"/products/{p.id}/price", json={"price": 1490.00})
    assert res.status_code == 200, res.text
    assert res.json()["price"] == 1490
    read = await stand.client.get(f"/products/{p.id}")
    assert read.json()["price"] == 1490


async def test_negative_price_is_rejected_with_field_name(stand):
    p = await mouse(stand)
    res = await stand.client.patch(f"/products/{p.id}/price", json={"price": -1})
    assert res.status_code == 400, res.text
    assert "price" in res.json()["errors"]


async def test_price_of_unknown_product_is_not_found(stand):
    missing = uuid.uuid4()
    res = await stand.client.patch(f"/products/{missing}/price", json={"price": 100.00})
    assert res.status_code == 404
    assert str(missing) in res.json()["detail"]


async def test_restock_increases_stock(stand):
    p = await mouse(stand)
    res = await stand.client.patch(f"/products/{p.id}/stock", json={"delta": 7})
    assert res.status_code == 200, res.text
    assert res.json()["stock"] == 12


async def test_write_off_below_zero_is_conflict(stand):
    p = await mouse(stand)
    res = await stand.client.patch(f"/products/{p.id}/stock", json={"delta": -9})
    assert res.status_code == 409, res.text
    read = await stand.client.get(f"/products/{p.id}")
    assert read.json()["stock"] == 5, "неудачное списание не должно менять остаток"


async def test_zero_delta_is_bad_request(stand):
    p = await mouse(stand)
    res = await stand.client.patch(f"/products/{p.id}/stock", json={"delta": 0})
    assert res.status_code == 400, res.text


async def test_missing_delta_is_rejected_with_field_name(stand):
    p = await mouse(stand)
    res = await stand.client.patch(f"/products/{p.id}/stock", json={})
    assert res.status_code == 400, res.text
    assert "delta" in res.json()["errors"]
