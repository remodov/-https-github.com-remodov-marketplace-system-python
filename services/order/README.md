# order

Order Service из сквозного маркетплейс-кейса сайта [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/case/order-service/):
оформление заказов. Сервис ходит за ценами в соседний `catalog` и с восьмого шага практикума умеет
переживать его медленные ответы, сорванные соединения и полное отсутствие.

**Уровень 3** методологии Use Case Pattern: агрегат `Order` с позициями и правилами внутри, команда и
обработчик сценария с явными портами, выходной адаптер к каталогу с таймаутами, повтором и размыкателем.
Статусная модель, идемпотентность, outbox и сага появляются на следующих шагах.

Спецификация в [`docs/spec/`](docs/spec/), контракт REST в [`docs/order.openapi.yaml`](docs/order.openapi.yaml).

## Как устроен сервис

```
order/main.py                           точка входа для uvicorn
order/
  core/
    errors.py                           ошибки с видом и кодом, общие для ядра и адаптеров
    security/                           Principal из токена, роли
    order/
      aggregate/                        Order и Item: поля закрыты, правила в методах, Money и Address
      port/out.py                       протоколы: репозиторий, шлюз каталога, часы, идентификаторы, единица работы
      usecase/                          команда CreateOrder и её обработчик
      query/                            чтение заказа с проверкой владения
  adapter/
    inbound/http/                       FastAPI: роутер, Problem Details, роли в зависимостях, схемы pydantic
    outbound/catalog/                   HTTP-клиент каталога на httpx: таймауты, повтор, размыкатель
    outbound/persistence/               SQLAlchemy Core, миграции Alembic, сессия в contextvar
    outbound/system/                    системные часы и uuid
  bootstrap/                            настройки, числа клиента каталога, сборка зависимостей, приложение
migrations/                             Alembic: orders, order_items
tests/                                  архитектурный, создание заказа, устойчивость к каталогу
```

Ядро не знает ни про FastAPI, ни про SQLAlchemy, ни про httpx: это стережёт `tests/test_architecture.py`.
Каталог для ядра - протокол `CatalogGateway`, который отдаёт цены или ошибку с кодом; как именно клиент
добывает цены и когда сдаётся, ядро не видит.

## Запуск

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter
python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -e ".[dev]"
(cd ../catalog && uvicorn catalog.main:app --port 8180 &)
uvicorn order.main:app --port 8181
```

Переменные: `HTTP_PORT` (`8181`), `DATABASE_URL` (`postgresql+asyncpg://catalog:catalog@localhost:5470/orders`),
`CATALOG_URL` (`http://localhost:8180`), `AUTH_MODE` (`local` или `jwt`), для `jwt` ещё `JWKS_URL`,
`JWT_ISSUER`, `JWT_AUDIENCE`.

В режиме `local` токен это строка `role.uuid`, роли `customer`, `seller`, `admin`:

```bash
CUSTOMER=$(uuidgen | tr A-Z a-z)
curl -s -X POST localhost:8181/api/v1/orders -H "Authorization: Bearer customer.$CUSTOMER" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"productId":"<id опубликованного товара>","sellerId":"<id продавца>","quantity":2}],
       "shippingAddress":{"country":"RU","city":"Москва","street":"Тверская, 1","postalCode":"125009"}}'
```

Товар должен быть опубликован в каталоге: черновики каталог отдаёт только владельцу, а заказ ходит без токена.

## Что происходит, когда каталог не отвечает

Клиент каталога (`order/adapter/outbound/catalog/client.py`), размыкатель рядом (`breaker.py`) и числа
(`catalog_settings` в `order/bootstrap/wire.py`):

| что | значение | зачем |
|---|---|---|
| таймаут соединения | 500 мс | не висеть на `connect`, если сосед не слушает |
| таймаут чтения | 1 с | медленный сосед не должен держать обработчик заказа |
| попытки | 2, пауза 50 мс | одна сорванная попытка не роняет оформление |
| размыкатель | пять сорванных вызовов подряд, открыт 60 с, потом одна проба | лежащему соседу не копить очередь запросов |

Повторяются только сетевые ошибки (`httpx.TransportError`, таймауты в том числе) и ответы 5xx. Ответ `404`
каталога это не отказ, а ответ: он без повтора становится `PRODUCT_NOT_FOUND` и размыкатель не трогает.
Исчерпанные попытки и открытый размыкатель уходят наружу как `503 SERVICE_DEGRADED`, заказ при этом не
создаётся. Худшее время ответа при этих числах: две попытки по секунде и пауза, около 2,05 с.

## Тесты

```bash
python -m pytest -q
```

Интеграционные тесты идут на настоящей PostgreSQL (`orders_test` из compose, `TEST_DATABASE_URL`):
приложение поднимается через lifespan и накатывает миграции. Каталог в тестах подменяется локальным
HTTP-сервером на `asyncio.start_server`, который умеет держать ответ, рвать соединение, отвечать 404 и
считать запросы: четыре проверки `test_catalog_*` закрывают повтор, лежащий каталог, таймаут и размыкатель.

## Коды ошибок

`VALIDATION_ERROR`, `MALFORMED_REQUEST`, `EMPTY_ORDER`, `MULTI_SELLER_NOT_SUPPORTED` (400), `TOKEN_MISSING`,
`TOKEN_INVALID` (401), `ACCESS_DENIED` (403), `PRODUCT_NOT_FOUND`, `ORDER_NOT_FOUND` (404),
`SERVICE_DEGRADED` (503). Тело ошибки в формате Problem Details, `type` вида `urn:problem:order:<CODE>`.

## Что почитать

- [Order Service в кейсе](https://vikulin-va.ru/use-case-pattern/case/order-service/) и [Use Case Pattern](https://vikulin-va.ru/use-case-pattern/).
- [Паттерны отказоустойчивости на Python](https://vikulin-va.ru/patterns/python/resilience/): повтор, таймаут, размыкатель.
- [Монолит и микросервисы](https://vikulin-va.ru/architecture-choice/monolith-vs-microservices/): цена сетевого вызова к соседу.
- [Гексагональная архитектура на Python](https://vikulin-va.ru/patterns/hexagonal/python/core-layer/): почему каталог для ядра - протокол.
