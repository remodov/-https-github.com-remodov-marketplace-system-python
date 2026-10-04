# order

Order Service из сквозного маркетплейс-кейса сайта [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/case/order-service/):
оформление заказов. Сервис ходит за ценами в соседний `catalog` и с восьмого шага практикума умеет
переживать его медленные ответы, сорванные соединения и полное отсутствие.

**Уровень 3** методологии Use Case Pattern: агрегат `Order` с позициями и правилами внутри, команда и
обработчик сценария с явными портами, выходной адаптер к каталогу с таймаутами, повтором и размыкателем.
С девятого шага создание заказа идемпотентно по заголовку `Idempotency-Key`, с десятого события уезжают соседям
через outbox и Kafka по внешнему контракту из [`contracts/`](../../contracts/), с одиннадцатого заказ живёт по
статусной модели, а отмена оплаченного заказа идёт сагой с возвратом денег через `payment`.

Спецификация в [`docs/spec/`](docs/spec/), контракт REST в [`docs/order.openapi.yaml`](docs/order.openapi.yaml).

## Как устроен сервис

```
order/main.py                           точка входа для uvicorn
order/
  core/
    errors.py                           ошибки с видом и кодом, общие для ядра и адаптеров
    security/                           Principal из токена, роли
    order/
      aggregate/                        Order и Item: поля закрыты, переходы статусов в методах, Money и Address, события
      port/out.py                       протоколы: репозиторий, шлюзы каталога и платежей, часы, идентификаторы, единица работы, outbox, издатель, processed_events
      usecase/                          CreateOrder, переходы статусов (LifecycleHandler), relay outbox, просрочка оплаты
      query/                            чтение заказа с проверкой владения
  adapter/
    inbound/http/                       FastAPI: роутер, Problem Details, роли в зависимостях, схемы pydantic
    inbound/kafka/                      потребитель PaymentCompleted: processed_events и перевод в PAID одной транзакцией
    outbound/catalog/                   HTTP-клиент каталога на httpx: таймауты, повтор, размыкатель
    outbound/payment/                   HTTP-клиент возврата в сервис платежей с Idempotency-Key
    outbound/persistence/               SQLAlchemy Core, миграции Alembic, сессия в contextvar, ключи идемпотентности, outbox, processed_events
    outbound/kafka/                     издатель событий на aiokafka: ключ, заголовки, acks=all
    outbound/system/                    системные часы, uuid и издатель в лог для разработки без Kafka
  bootstrap/                            настройки, числа клиентов и фоновых задач, сборка зависимостей, приложение
migrations/                             Alembic: orders, order_items, idempotency_keys, outbox, жизненный цикл и processed_events
tests/                                  архитектурный, создание заказа, устойчивость к каталогу, идемпотентность, outbox, Kafka, жизненный цикл
```

Ядро не знает ни про FastAPI, ни про SQLAlchemy, ни про httpx, ни про aiokafka, ни про пакет внешнего контракта:
это стережёт `tests/test_architecture.py`. Каталог для ядра - протокол `CatalogGateway`, который отдаёт цены или
ошибку с кодом; как именно клиент добывает цены и когда сдаётся, ядро не видит. Так же устроены `EventOutbox` и
`ExternalEventPublisher`.

## Запуск

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter kafka
python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -e ../../contracts/orders_v1 -e ../../contracts/payments_v1 -e ".[dev]"
(cd ../catalog && uvicorn catalog.main:app --port 8180 &)
(cd ../payment && uvicorn payment.main:app --port 8186 &)
uvicorn order.main:app --port 8181
```

Переменные: `HTTP_PORT` (`8181`), `DATABASE_URL` (`postgresql+asyncpg://catalog:catalog@localhost:5470/orders`),
`CATALOG_URL` (`http://localhost:8180`), `PAYMENT_URL` (`http://localhost:8186`), `KAFKA_BROKERS` (`localhost:9097`),
`KAFKA_TOPIC` (`marketplace.orders.v1`), `KAFKA_GROUP` (`order`), `PAYMENTS_TOPIC` (`marketplace.payments.v1`),
`EVENT_PUBLISHER` (`kafka` или `log`: без Kafka события только пишутся в лог), `OUTBOX_RELAY_ENABLED` (`true`),
`OUTBOX_RELAY_INTERVAL_SECONDS` (`1`), `PAYMENT_CONSUMER_ENABLED` (`true`; без Kafka выключи),
`EXPIRE_UNPAID_ENABLED` (`true`), `EXPIRE_UNPAID_AFTER_SECONDS` (`900`), `EXPIRE_INTERVAL_SECONDS` (`60`),
`AUTH_MODE` (`local` или `jwt`), для `jwt` ещё `JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`.

В режиме `local` токен это строка `role.uuid`, роли `customer`, `seller`, `admin`:

```bash
CUSTOMER=$(uuidgen | tr A-Z a-z)
curl -s -X POST localhost:8181/api/v1/orders -H "Authorization: Bearer customer.$CUSTOMER" \
  -H "Idempotency-Key: $(uuidgen)" -H 'Content-Type: application/json' \
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

## Один запрос - один заказ

Заголовок `Idempotency-Key` обязателен. Сценарий сначала ищет ключ: тот же ключ с тем же хешем тела отдаёт
прежний заказ ответом 200, тот же ключ с другим телом - `409 IDEMPOTENCY_KEY_CONFLICT`. Если ключа нет, заказ и
ключ пишутся в одной единице работы (`async with uow.begin()`), ключ занимается вставкой с
`ON CONFLICT DO NOTHING`: при гонке второй `INSERT` дожидается первой транзакции, получает ноль строк,
исключением откатывает свой заказ и читает чужой. Тест `test_idempotency_same_key_at_once_creates_one_order`
шлёт восемь одинаковых запросов разом через `asyncio.gather` и ждёт один заказ. Хеш тела считается в
HTTP-адаптере как SHA-256 канонического JSON разобранного запроса (`model_dump_json`), в ядро доезжает уже
строкой.

## Событие уезжает через outbox

Агрегат при создании регистрирует `OrderCreated` (`order/core/order/aggregate/events.py`); обработчик сценария
забирает события `pull_events()` и кладёт их в таблицу `outbox` в той же единице работы, что заказ и ключ
идемпотентности. Фоновая задача relay (`OutboxRelay.run` в `order/core/order/usecase/relay_outbox.py`) раз в
`OUTBOX_RELAY_INTERVAL_SECONDS` берёт пачку строк с `published_at IS NULL` под `FOR UPDATE SKIP LOCKED`,
публикует каждую через порт `ExternalEventPublisher` и помечает отправленной в той же транзакции; упал брокер -
транзакция откатилась, строки остались, следующий круг повторит. Остановка сервиса в lifespan не рвёт пачку:
`relay.stop()` запрещает новый круг, а задача дожидается конца текущего.

Payload строки это внешний контракт, а не дамп внутреннего класса: `payload_of` в
`order/adapter/outbound/persistence/outbox_repository.py` собирает `OrderCreatedPayload` из пакета
[`contracts/orders_v1`](../../contracts/orders_v1/orders_v1/events.py) - `customerId` строкой, сумма десятичной
строкой, ничего лишнего. Издатель `adapter/outbound/kafka` пишет в топик `marketplace.orders.v1` с ключом
`aggregateId` и заголовками `event-id`, `event-type`, `event-version`, `aggregate-type`, `aggregate-id`,
`occurred-at`; по `event-id` потребитель отбрасывает повторную доставку. Продюсер aiokafka создаётся в `start()`
внутри lifespan: конструктор клиента требует запущенный цикл событий, а `create_app()` вызывается при импорте.

## Статусы и сага отмены

Переходы живут в агрегате и перечисляют разрешённое: `confirm` DRAFT -> PENDING_PAYMENT (не меньше 100 рублей,
иначе `ORDER_BELOW_MINIMUM`), `mark_paid` -> PAID, `mark_shipped` -> SHIPPED, `confirm_delivery` -> DELIVERED,
`cancel` из DRAFT и PENDING_PAYMENT, `cancel_after_payment` из PAID, `expire` из PENDING_PAYMENT. Всё остальное
отвечает `409 ORDER_INVALID_STATE` и данные не трогает. Каждый переход - одна единица работы
(`LifecycleHandler._transition` в `order/core/order/usecase/lifecycle.py`): строка под `FOR UPDATE`, метод агрегата,
`UPDATE`, события в outbox.

Ручки: `POST /api/v1/orders/{id}/confirm`, `/cancel` (покупатель или администратор), `/ship` (продавец заказа),
`/deliver` (покупатель), `/pay` (только администратор, для стенда; в бою оплату приносит событие `PaymentCompleted`
из топика `marketplace.payments.v1`, потребитель `order/adapter/inbound/kafka/payment_consumer.py` отбрасывает
повтор по `event-id` через `processed_events` в той же транзакции, что и перевод в PAID).

Отмена оплаченного заказа - сага с компенсацией: обработчик внутри транзакции зовёт сервис платежей
`POST /api/v1/payments/{paymentId}/refund` с `Idempotency-Key: refund-<orderId>` (клиент
`order/adapter/outbound/payment/client.py`, таймауты 500 мс на соединение и 2 с на ответ) и только после успешного
возврата переводит заказ в CANCELLED с `refundId` в событии `OrderCancelled`. Платежи легли - `503 SERVICE_DEGRADED`,
транзакция откатилась, заказ остался PAID, повтор отмены безопасен: платежи повторный возврат не считают вторым.
Неоплаченный заказ закрывает фоновая задача `ExpireUnpaid` (`order/core/order/usecase/expire_unpaid.py`): раз в
`EXPIRE_INTERVAL_SECONDS` переводит в EXPIRED те, что висят в PENDING_PAYMENT дольше `EXPIRE_UNPAID_AFTER_SECONDS`.

## Сквозной прогон

Четыре сервиса из одного окружения: `catalog` на 8180, `order` на 8181, `notification` на 8185, `payment` на 8186;
стенд с PostgreSQL и Kafka поднят. Сага отмены с возвратом описана в `README.md` сервиса платежей, раздел
«Сквозной прогон».

```bash
(cd ../catalog && uvicorn catalog.main:app --port 8180 &)
(cd ../notification && uvicorn notification.main:app --port 8185 &)
(cd ../payment && uvicorn payment.main:app --port 8186 &)
uvicorn order.main:app --port 8181 &
SELLER=$(uuidgen | tr A-Z a-z); CUSTOMER=$(uuidgen | tr A-Z a-z)
PRODUCT=$(curl -s -X POST localhost:8180/api/v1/products -H "Authorization: Bearer seller.$SELLER" \
  -H 'Content-Type: application/json' -d '{"title":"Кофемолка","price":2490.5,"currency":"RUB"}' | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
curl -s -o /dev/null -X POST localhost:8180/api/v1/products/$PRODUCT/publish -H "Authorization: Bearer seller.$SELLER"
curl -s -X POST localhost:8181/api/v1/orders -H "Authorization: Bearer customer.$CUSTOMER" -H "Idempotency-Key: $(uuidgen)" \
  -H 'Content-Type: application/json' \
  -d "{\"items\":[{\"productId\":\"$PRODUCT\",\"sellerId\":\"$SELLER\",\"quantity\":2}],\"shippingAddress\":{\"country\":\"RU\",\"city\":\"Москва\",\"street\":\"Тверская, 1\",\"postalCode\":\"125009\"}}"
sleep 3
curl -s "localhost:8185/api/v1/notifications?userId=$CUSTOMER" -H 'Authorization: Bearer admin'
```

Что получается: заказ отвечает `201` с `total` 4981.0, повтор с тем же `Idempotency-Key` и телом - `200` с тем же
`id`, второй строки в `outbox` нет. Через пару секунд `notification` отдаёт одно уведомление покупателю:
`eventType` `OrderCreated`, `templateKey` `order-created`, `status` `PENDING`. В базе `orders` строка outbox помечена
`published_at`, её payload ровно семь полей контракта; в базе `notifications` одна запись `processed_events` с тем
же `event-id`. Без токена `notification` отвечает `403 ACCESS_DENIED`, на `userId=abc` - `400 VALIDATION_ERROR`.
Если `notification` стартовал раньше первого заказа, в его логе один раз мелькнёт `Topic marketplace.orders.v1 not
found in cluster metadata`: топик создаёт первая публикация, консьюмер подхватывает его сам.

## Тесты

```bash
python -m pytest -q
```

Интеграционные тесты идут на настоящей PostgreSQL (`orders_test` из compose, `TEST_DATABASE_URL`):
приложение поднимается через lifespan и накатывает миграции, relay в тестах не крутится сам
(`outbox_relay_enabled=False`), издатель подменяется записывающей заглушкой. Каталог в тестах подменяется
локальным HTTP-сервером на `asyncio.start_server`, который умеет держать ответ, рвать соединение, отвечать 404 и
считать запросы: четыре проверки `test_catalog_*` закрывают повтор, лежащий каталог, таймаут и размыкатель,
пять `test_idempotency_*` и соседний тест без заголовка - повтор, конфликт тела, разные ключи, гонку и
обязательность `Idempotency-Key`. Пять `test_outbox_*` проверяют строку рядом с заказом, поля payload по контракту,
повтор без второго события, relay и лежащий брокер; `test_kafka_publisher_*` ждёт Kafka со стенда и пропускается с
подсказкой, если брокер не поднят. Девять `test_lifecycle_*` проходят заказ от черновика до получения, отмену с
возвратом через подменный сервис платежей (`FakePayment` в `conftest.py` записывает запросы и умеет лечь), просрочку
оплаты на подкручиваемых часах; `test_payment_consumer_*` дважды отдаёт обработчику одно и то же `PaymentCompleted`
и ждёт один `OrderPaid`.

## Коды ошибок

`VALIDATION_ERROR`, `MALFORMED_REQUEST`, `EMPTY_ORDER`, `MULTI_SELLER_NOT_SUPPORTED` (400), `TOKEN_MISSING`,
`ORDER_BELOW_MINIMUM` (400), `TOKEN_INVALID` (401), `ACCESS_DENIED` (403), `PRODUCT_NOT_FOUND`, `ORDER_NOT_FOUND` (404),
`IDEMPOTENCY_KEY_CONFLICT`, `ORDER_INVALID_STATE`, `REFUND_REJECTED`, `PAYMENT_NOT_FOUND` (409), `SERVICE_DEGRADED` (503).
Тело ошибки в формате Problem Details, `type` вида `urn:problem:order:<CODE>`.

## Что почитать

- [Order Service в кейсе](https://vikulin-va.ru/use-case-pattern/case/order-service/) и [Use Case Pattern](https://vikulin-va.ru/use-case-pattern/).
- [Паттерны отказоустойчивости на Python](https://vikulin-va.ru/patterns/python/resilience/): повтор, таймаут, размыкатель.
- [Монолит и микросервисы](https://vikulin-va.ru/architecture-choice/monolith-vs-microservices/): цена сетевого вызова к соседу.
- [Гексагональная архитектура на Python](https://vikulin-va.ru/patterns/hexagonal/python/core-layer/): почему каталог для ядра - протокол.
- [HTTP-заголовки и Idempotency-Key на Python](https://vikulin-va.ru/rest-api/python/headers/): ключ занимается до операции.
- [Распределённые паттерны на Python](https://vikulin-va.ru/patterns/python/distributed-patterns/): outbox и идемпотентный потребитель.
- [asyncio-задачи и outbox-relay при остановке](https://vikulin-va.ru/graceful-shutdown/python/scheduled-async-outbox/).
- [Конечные автоматы на Python](https://vikulin-va.ru/state-machines/python/implementation/): переходы перечислены разрешёнными.
