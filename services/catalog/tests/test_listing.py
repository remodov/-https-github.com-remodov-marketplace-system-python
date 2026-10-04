import uuid


async def test_list_products_shows_only_published_to_everyone(stand):
    await stand.clear_tables()
    seller = uuid.uuid4()
    published = await stand.given_product(seller, "PUBLISHED", "1990.00")
    await stand.given_product(seller, "DRAFT", "100.00")
    await stand.given_product(seller, "HIDDEN", "200.00")

    res = await stand.call("GET", "/api/v1/products?sort=price,asc")

    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["items"]) == 1 and body["total"] == 1, "на витрине должен быть один опубликованный товар"
    first = body["items"][0]
    assert first["id"] == str(published) and first["sellerId"] == str(seller), (
        "карточка витрины должна нести идентификатор товара и продавца"
    )
