import uuid


async def test_rate_limit_fourth_request_in_a_minute_is_rejected(start_stand):
    stand = await start_stand(per_minute=3)
    client = str(uuid.uuid4())

    for attempt in range(1, 4):
        res = await stand.screen(client)
        assert res.status_code != 429, f"запрос {attempt} не должен упираться в лимит"
    rejected = await stand.screen(client)

    assert rejected.status_code == 429, (
        f"четвёртый запрос должен получить 429, получили {rejected.status_code}"
    )
    assert rejected.headers.get("Retry-After"), "при 429 нужен Retry-After"
    assert rejected.headers.get("X-RateLimit-Remaining") == "0", dict(rejected.headers)
    assert rejected.json()["code"] == "RATE_LIMITED", rejected.text


async def test_rate_limit_counts_per_client(start_stand):
    stand = await start_stand(per_minute=3)
    noisy, quiet = str(uuid.uuid4()), str(uuid.uuid4())

    for _ in range(4):
        await stand.screen(noisy)
    res = await stand.screen(quiet)

    assert res.status_code != 429, "сосед не должен расходовать чужую квоту"
