# bff

Backend for frontend из сквозного маркетплейс-кейса сайта [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/case/):
тонкий слой на границе системы. Клиент просит **экран**, а не три ресурса из трёх сервисов: мобильному
приложению три круговые задержки дороже, чем одна. Здесь же живёт то, что положено границе: лимит частоты и
внятный ответ, когда сосед не отвечает. В практикуме на Python появляется на тринадцатом шаге; сборка экрана
и счётчик лимита - задание ученика.

Нарочно простой сервис, как `payment`: один пакет, без базы и портов; состояние только в Redis.

```
bff/main.py        точка входа для uvicorn
bff/
  config.py        переменные окружения
  downstream.py    DownstreamClient: поход к соседу с таймаутом, ответ разбирается в модель, отказ это DownstreamError
  screen.py        ScreenAssembler: заказ первым, затем карточки товаров и статус платежа одновременно
  ratelimit.py     Limiter: счётчик в Redis на минутное окно; RateLimitMiddleware: 429 и Retry-After
  errors.py        ScreenNotAssembled и DownstreamError
  httpapi.py       FastAPI: ручка экрана, Problem Details, health
  problem.py       тело ошибки в формате Problem Details
tests/             соседи подменены локальными HTTP-серверами, Redis настоящий
```

## Экран заказа

```
GET /api/v1/screens/order/{orderId}   заголовки Authorization и X-Client-Id
```

```json
{"orderId":"...","status":"PAID","total":4981.0,"paymentStatus":"NONE",
 "items":[{"productId":"...","title":"Кофемолка","quantity":2,"price":2490.5}]}
```

`ScreenAssembler.assemble` читает заказ у `order`, из него знает товары и `paymentId`. Дальше карточки товаров
из `catalog` и статус платежа из `payment` добираются **одновременно** через `asyncio.gather`: экран ждёт
самый медленный ответ, а не сумму всех. Платежа может не быть вовсе: заказ ещё не оплачивали, `paymentId`
пустой или `payment` отвечает 404. Это обычное состояние экрана (`paymentStatus: NONE`), а не ошибка.

Токен клиента BFF пересылает соседям как есть: заказ отдаёт только своему покупателю, и решает это сервис
заказов, а не граница. Бизнес-правил здесь нет, только сборка.

Коды ошибок: `VALIDATION_ERROR` (400, `orderId` не UUID), `ORDER_NOT_FOUND` (404) и `ORDER_ACCESS_DENIED`
(401 или 403) пробрасываются от `order`; любой другой отказ соседа (не слушает, таймаут, 5xx, нечитаемый
ответ) это `502 DOWNSTREAM_UNAVAILABLE`, а не пятисотка без объяснений. Тело в формате Problem Details,
`type` вида `urn:problem:bff:<CODE>`.

## Лимит частоты

Клиент определяется заголовком `X-Client-Id`, без него все анонимные делят одну квоту `anonymous`.
`Limiter.check` держит в Redis ключ `rate:<client>:<номер минутного окна>`: `INCR`, на первом попадании
`EXPIRE` на окно, ключ протухает сам, отдельной чистки нет. Счётчик общий для всех экземпляров границы:
в памяти процесса лимит тихо умножался бы на их число.

`RateLimitMiddleware` стоит на `/api/`, здоровье не считает. Каждый ответ несёт `X-RateLimit-Remaining`;
при превышении `429 RATE_LIMITED` с `Retry-After`. Если Redis недоступен, запрос пропускается с
предупреждением в логе: граница без счётчика лучше границы, которая не отвечает никому.

## Запуск и тесты

```bash
docker compose -f ../../infra/compose.yaml up -d redis
pip install -e ".[dev]"
uvicorn bff.main:app --port 8190
python -m pytest -q
```

Переменные: `HTTP_PORT` (`8190`), `REDIS_URL` (`redis://localhost:6383`), `ORDER_URL` (`http://localhost:8181`),
`CATALOG_URL` (`http://localhost:8180`), `PAYMENT_URL` (`http://localhost:8186`), `RATE_LIMIT_PER_MINUTE` (`60`).

Соседи в тестах подменены локальными HTTP-серверами на `asyncio.start_server`, которые считают запросы и
запоминают заголовок `Authorization`; Redis нужен настоящий (`TEST_REDIS_URL`, по умолчанию база `/1` на
стенде): счётчик и должен быть общим, а не в памяти процесса. Клиенты в тестах случайные, прогоны друг
другу не мешают.

## Сквозной прогон

Четыре сервиса из одного окружения: `catalog` на 8180, `order` на 8181, `payment` на 8186, `bff` на 8190;
стенд с PostgreSQL и Redis поднят. Товар и заказ создаются как в `README.md` сервиса заказов, экран
спрашивается через BFF токеном покупателя:

```bash
SELLER=$(uuidgen | tr A-Z a-z); CUSTOMER=$(uuidgen | tr A-Z a-z)
PRODUCT=$(curl -s -X POST localhost:8180/api/v1/products -H "Authorization: Bearer seller.$SELLER" \
  -H 'Content-Type: application/json' -d '{"title":"Кофемолка","price":2490.5,"currency":"RUB"}' | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
curl -s -o /dev/null -X POST localhost:8180/api/v1/products/$PRODUCT/publish -H "Authorization: Bearer seller.$SELLER"
ORDER=$(curl -s -X POST localhost:8181/api/v1/orders -H "Authorization: Bearer customer.$CUSTOMER" -H "Idempotency-Key: $(uuidgen)" \
  -H 'Content-Type: application/json' \
  -d "{\"items\":[{\"productId\":\"$PRODUCT\",\"sellerId\":\"$SELLER\",\"quantity\":2}],\"shippingAddress\":{\"country\":\"RU\",\"city\":\"Москва\",\"street\":\"Тверская, 1\",\"postalCode\":\"125009\"}}" | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
curl -s -i -H 'X-Client-Id: demo' -H "Authorization: Bearer customer.$CUSTOMER" localhost:8190/api/v1/screens/order/$ORDER
```

Что получается: один запрос клиента, в ответе `status: DRAFT`, `total: 4981.0`, строка с названием
«Кофемолка», количеством 2 и ценой 2490.5 из каталога и `paymentStatus: NONE`, потому что заказ ещё не
оплачивали; в заголовках `X-RateLimit-Remaining: 59`. Чужой покупатель и несуществующий заказ получают
`404 ORDER_NOT_FOUND`: сервис заказов не выдаёт чужой заказ даже как существующий, и BFF это решение не
переписывает; без токена `401 ORDER_ACCESS_DENIED`; `abc` вместо идентификатора `400 VALIDATION_ERROR`.
Урони `catalog` (`pkill -f catalog.main:app`) и повтори: `502 DOWNSTREAM_UNAVAILABLE` за десятки
миллисекунд, соединение отвергнуто без ожидания таймаута, в логе BFF предупреждение «экран заказа не собран».

Перезапусти BFF с `RATE_LIMIT_PER_MINUTE=3` и спроси экран четыре раза с одним `X-Client-Id`: три ответа
`200` с `X-RateLimit-Remaining` 2, 1, 0, четвёртый `429 RATE_LIMITED` с `Retry-After: 60`; другой
`X-Client-Id` в ту же минуту получает `200`. В Redis виден один ключ `rate:demo:<окно>` со значением 4 и
`TTL` меньше минуты.

## Что почитать

- [Структурные паттерны микросервисов на Python](https://vikulin-va.ru/patterns/python/microservices-structural/): API Gateway, BFF и почему не «универсальный» ресурс.
- [Стили API](https://vikulin-va.ru/api-styles/): откуда берётся проблема трёх запросов.
- [Лимит частоты, файлы и устаревание в REST API на Python](https://vikulin-va.ru/rest-api/python/rate-limiting-files-deprecation/): 429, `Retry-After` и заголовки остатка.
- [redis-py](https://vikulin-va.ru/redis/python/redis-py/): счётчики с протуханием.
