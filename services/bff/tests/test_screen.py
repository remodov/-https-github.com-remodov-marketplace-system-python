from conftest import expect


async def test_screen_assembled_from_three_services(start_stand):
    stand = await start_stand()

    body = expect(await stand.screen(), 200)

    assert body["status"] == "PAID" and body["paymentStatus"] == "CAPTURED", body
    assert [(item["title"], item["quantity"], item["price"]) for item in body["items"]] == [
        ("Беспроводная мышь", 2, 1990.0)
    ], body["items"]
    calls = (stand.stubs.order.calls, stand.stubs.catalog.calls, stand.stubs.payment.calls)
    assert calls == (1, 1, 1), (
        f"ожидали по одному походу к каждому соседу, получили order, catalog, payment = {calls}"
    )
    assert stand.stubs.order.authorizations == [stand.authorization], "токен клиента уходит соседям как есть"


async def test_screen_survives_missing_payment(start_stand):
    stand = await start_stand(payment_status=404)

    body = expect(await stand.screen(), 200)

    assert body["paymentStatus"] == "NONE", body
    assert [item["title"] for item in body["items"]] == ["Беспроводная мышь"], body


async def test_screen_downstream_down_is_bad_gateway(start_stand):
    stand = await start_stand()
    await stand.stubs.catalog.close()

    body = expect(await stand.screen(), 502)

    assert body["code"] == "DOWNSTREAM_UNAVAILABLE", body
