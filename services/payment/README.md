# payment

Payment Service из сквозного маркетплейс-кейса сайта [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/case/):
авторизация, списание и возврат платежа по заказу. В практикуме на Python появляется на одиннадцатом шаге как сервис,
в который ходит сага отмены заказа; это задание ученика.

Нарочно самый простой сервис из всех: один пакет, `asyncpg` напрямую с SQL и маппингом руками, схема из
`schema.sql` при старте вместо миграций. Сравни с соседями: `catalog-starter` на ORM-репозиториях SQLAlchemy,
`catalog` и `order` на SQLAlchemy Core с портами, единицей работы и Alembic. Что каждый из них скрывает и что даёт?

```
payment/main.py        точка входа для uvicorn
payment/
  config.py            переменные окружения
  model.py             Status с автоматом переходов, Payment.move_to, ошибки InvalidTransition и PaymentNotFound
  repository.py        пул asyncpg, схема при старте, SQL руками: выбор, блокировка строки, вставка, смена статуса
  service.py           авторизация, списание, возврат; транзакция на операцию
  httpapi.py           FastAPI: ручки, Problem Details, health
  schema.sql           таблица payments
tests/                 автомат без базы, API на настоящей PostgreSQL
```

## Автомат статусов

У платежа четыре статуса: `AUTHORIZED`, `CAPTURED`, `REFUNDED`, `FAILED`. `Status.can_move_to` перечисляет
**разрешённое**: `AUTHORIZED -> CAPTURED | REFUNDED | FAILED`, `CAPTURED -> REFUNDED`; конечные статусы никуда не
ведут, переход в себя же не переход. Всё остальное `Payment.move_to` отвергает ошибкой `InvalidTransition`,
наружу это `409 INVALID_PAYMENT_TRANSITION`.

Повторы саги обрабатываются в сервисе, а не в автомате: повторная авторизация того же заказа возвращает уже
созданный платёж (`order_id` уникален), повторный возврат отдаёт тот же ответ, а деньги возвращаются один раз.
Переход читает строку под `FOR UPDATE`: два параллельных запроса на один платёж не проскочат автомат вдвоём.

## Ручки

```
POST /api/v1/payments               {"orderId","amount","currency"} -> 201, AUTHORIZED
GET  /api/v1/payments/{id}
POST /api/v1/payments/{id}/capture  -> CAPTURED
POST /api/v1/payments/{id}/refund   -> REFUNDED, повтор безопасен
```

Сумма в ответе числом, как у заказа. Коды ошибок: `VALIDATION_ERROR`, `MALFORMED_REQUEST` (400), `PAYMENT_NOT_FOUND`
(404), `INVALID_PAYMENT_TRANSITION` (409), `NOT_READY` (503). Тело в формате Problem Details, `type` вида
`urn:problem:payment:<CODE>`.

События платежа сервис пока не публикует: контракт `contracts/payments_v1` (`PaymentCompleted`) читает `order`,
а на стенде оплату отмечает администратор ручкой `POST /api/v1/orders/{id}/pay`.

## Запуск и тесты

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter
pip install -e ".[dev]"
uvicorn payment.main:app --port 8186
python -m pytest -q
```

Переменные: `HTTP_PORT` (`8186`), `DATABASE_URL` (`postgresql://catalog:catalog@localhost:5470/payments`).
Тесты автомата (`tests/test_transitions.py`) идут без базы, тесты API (`tests/test_api.py`) - на настоящей PostgreSQL
(`payments_test` из compose, `TEST_DATABASE_URL`): приложение поднимается через lifespan, пул и схема создаются там же.
Пул asyncpg требует запущенный цикл событий уже в конструкторе, поэтому `Database.start()` зовётся в lifespan, а не при
импорте.

## Сквозной прогон

Четыре сервиса из одного окружения: `catalog` на 8180, `order` на 8181, `notification` на 8185, `payment` на 8186;
стенд с PostgreSQL и Kafka поднят. Товар и заказ создаются как в `README.md` сервиса заказов, дальше сага руками:

```bash
ORDER=<id заказа>; CUSTOMER=<uuid покупателя>; ADMIN=$(uuidgen | tr A-Z a-z)
curl -s -X POST localhost:8181/api/v1/orders/$ORDER/confirm -H "Authorization: Bearer customer.$CUSTOMER"
PAYMENT=$(curl -s -X POST localhost:8186/api/v1/payments -H 'Content-Type: application/json' \
  -d "{\"orderId\":\"$ORDER\",\"amount\":4981.00,\"currency\":\"RUB\"}" | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
curl -s -X POST localhost:8186/api/v1/payments/$PAYMENT/capture
curl -s -X POST localhost:8181/api/v1/orders/$ORDER/pay -H "Authorization: Bearer admin.$ADMIN" \
  -H 'Content-Type: application/json' -d "{\"paymentId\":\"$PAYMENT\"}"
curl -s -X POST localhost:8181/api/v1/orders/$ORDER/cancel -H "Authorization: Bearer customer.$CUSTOMER" \
  -H 'Content-Type: application/json' -d '{"reasonCode":"changed_mind","comment":"передумал"}'
curl -s localhost:8186/api/v1/payments/$PAYMENT
```

Что получается: заказ идёт `DRAFT -> PENDING_PAYMENT -> PAID -> CANCELLED`, платёж `AUTHORIZED -> CAPTURED ->
REFUNDED`; повторная авторизация того же заказа отдаёт тот же `id` и в базе одна строка; повторный возврат отвечает
`REFUNDED` с тем же `updatedAt`; списание возвращённого платежа - `409 INVALID_PAYMENT_TRANSITION`, статус не
портится; повторная отмена заказа - `409 ORDER_INVALID_STATE`. В outbox заказа четыре строки по заказу, все помечены
отправленными, у `OrderCancelled` в payload `previousStatus: PAID` и `refundId` платежа; `notification` заводит
покупателю четыре уведомления: `order-created`, `order-status-changed`, `order-paid`, `order-status-changed`.

Теперь урони `payment` (`pkill -f payment.main:app`) и повтори отмену другого оплаченного заказа: ответ
`503 SERVICE_DEGRADED` за 50 мс, заказ остался `PAID` с прежним `paymentId`, строки `OrderCancelled` в outbox нет,
в логе заказа одна строка «сосед недоступен ... All connection attempts failed». Подними `payment` обратно и повтори
ту же отмену: `CANCELLED`, платёж `REFUNDED`. Сага повторяется, деньги возвращаются один раз.

## Что почитать

- [Распределённые паттерны на Python](https://vikulin-va.ru/patterns/python/distributed-patterns/): сага и компенсации.
- [Конечные автоматы на Python](https://vikulin-va.ru/state-machines/python/implementation/): переходы перечислены разрешёнными.
- [Паттерны отказоустойчивости на Python](https://vikulin-va.ru/patterns/python/resilience/): как сосед переживает отказ платежей.
