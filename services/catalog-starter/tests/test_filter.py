from conftest import unique


async def test_cheaper_than_filter(stand):
    prefix = unique("Фильтр")
    expensive = await stand.must_create(f"{prefix} дорогой", "2500.00", 1)
    cheap = await stand.must_create(f"{prefix} дешёвый", "1990.00", 1)
    boundary = await stand.must_create(f"{prefix} ровно по границе", "2000.00", 1)

    res = await stand.client.get("/products", params={"maxPrice": "2000"})
    assert res.status_code == 200, res.text
    found = res.json()
    prices = [card["price"] for card in found]
    assert all(price <= 2000 for price in prices), "в выдаче товар дороже границы"
    assert prices == sorted(prices), "выдача не по возрастанию цены"
    ids = {card["id"] for card in found}
    assert str(cheap.id) in ids, "дешёвый товар не попал в выдачу"
    assert str(boundary.id) in ids, "товар ровно за maxPrice должен попадать: граница включающая"
    assert str(expensive.id) not in ids, "дорогой товар попал в выдачу"

    everything = await stand.client.get("/products")
    assert str(expensive.id) in {card["id"] for card in everything.json()}


async def test_garbage_in_max_price_gives_400_with_field(stand):
    res = await stand.client.get("/products", params={"maxPrice": "дорого"})
    assert res.status_code == 400, res.text
    assert "maxPrice" in res.json()["errors"]
