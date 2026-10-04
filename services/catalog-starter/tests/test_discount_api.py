from conftest import unique


async def test_discount_is_applied(stand):
    p = await stand.must_create(unique("Беспроводная мышь"), "1990.00", 5)
    res = await stand.client.patch(f"/products/{p.id}/discount", json={"percent": 20})
    assert res.status_code == 200, res.text
    assert res.json()["price"] == 1592


async def test_too_deep_discount_is_rejected(stand):
    p = await stand.must_create(unique("Беспроводная мышь"), "1990.00", 5)
    res = await stand.client.patch(f"/products/{p.id}/discount", json={"percent": 80})
    assert res.status_code == 400, res.text
    assert "50" in res.json()["detail"], "отказ должен назвать предел скидки"
    read = await stand.client.get(f"/products/{p.id}")
    assert read.json()["price"] == 1990, "неудачная скидка изменила цену"
