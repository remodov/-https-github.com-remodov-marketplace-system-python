import uuid

from conftest import unique


async def test_created_product_is_returned_by_id(stand):
    created = await stand.client.post("/products", json={"title": "Беспроводная мышь", "price": 1990.00, "stock": 7})
    assert created.status_code == 201, created.text
    assert created.json()["title"] == "Беспроводная мышь"
    read = await stand.client.get(f"/products/{created.json()['id']}")
    assert read.status_code == 200
    assert read.json()["stock"] == 7


async def test_search_finds_by_part_of_title(stand):
    title = unique("Механическая клавиатура")
    await stand.must_create(title, "5400.00", 3)
    part = title[len("Механическая ") :]
    res = await stand.client.get("/products", params={"query": part})
    assert res.status_code == 200
    assert [c["title"] for c in res.json()] == [title]


async def test_reserve_holds_stock_instead_of_writing_it_off(stand):
    p = await stand.must_create(unique("USB-хаб"), "890.00", 5)
    res = await stand.client.post(f"/products/{p.id}/reserve", json={"quantity": 2})
    assert res.status_code == 200, res.text
    card = res.json()
    assert (card["stock"], card["reserved"], card["available"]) == (5, 2, 3), "резерв удерживает, а не списывает"


async def test_reserve_more_than_stock_is_rejected(stand):
    p = await stand.must_create(unique("Коврик"), "450.00", 1)
    res = await stand.client.post(f"/products/{p.id}/reserve", json={"quantity": 4})
    assert res.status_code == 409


async def test_unknown_product_gives_not_found(stand):
    res = await stand.client.get(f"/products/{uuid.uuid4()}")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    assert "не найден" in res.json()["detail"]
