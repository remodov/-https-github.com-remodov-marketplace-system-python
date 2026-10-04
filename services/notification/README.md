# notification

Notification Service из сквозного маркетплейс-кейса сайта [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/case/notification-service/):
читает события заказа из Kafka и заводит уведомления адресату. В практикуме на Python появляется на десятом шаге как
потребитель outbox сервиса заказов; доставка писем и push тут не реализована, уведомление остаётся в статусе `PENDING`.

## Как устроен сервис

```
notification/main.py          точка входа для uvicorn
notification/
  config.py                   переменные окружения
  database.py                 движок, миграции Alembic, проверка базы для health
  tables.py                   processed_events и notifications
  inbox.py                    идемпотентная обработка: processed_events и уведомление в одной транзакции
  consumer.py                 AIOKafkaConsumer: заголовки event-id и event-type, commit после обработки
  httpapi.py                  GET /api/v1/notifications?userId= для администратора, health
  app.py                      сборка приложения, консьюмер как фоновая задача в lifespan
migrations/                   Alembic: processed_events, notifications
tests/                        обработка на настоящей PostgreSQL
```

Контракт событий общий с продюсером: пакет [`contracts/orders_v1`](../../contracts/orders_v1/orders_v1/events.py).
Payload читается в `OrderEventBase`; адресат берётся из `customerId`, у `DisputeOpened` - из `sellerId`.
Payload не по контракту (например, `customerId` вложенным объектом или без адресата) это ошибка обработки
`OffContract`: offset не сдвигается, в `processed_events` записи нет.

## Повторная доставка

Kafka доставляет как минимум один раз: перебалансировка группы, повтор relay после сбоя пометки. Поэтому перед
работой консьюмер вставляет `event-id` в `processed_events` с `ON CONFLICT DO NOTHING` в той же транзакции, что и
уведомление. Второй раз вставка даёт ноль строк, второе письмо не рождается.

Консьюмер создаётся с `enable_auto_commit=False` и фиксирует offset сам, после того как транзакция обработки
закоммичена: `consumer.commit({TopicPartition(...): record.offset + 1})`. Заголовки у aiokafka приходят
кортежами `(str, bytes)`, значения нужно декодировать.

## Запуск

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter kafka
pip install -e ../../contracts/orders_v1 -e ".[dev]"
uvicorn notification.main:app --port 8185
curl -s 'localhost:8185/api/v1/notifications?userId=<uuid покупателя>' -H 'Authorization: Bearer admin'
```

Переменные: `HTTP_PORT` (`8185`), `DATABASE_URL` (`postgresql+asyncpg://catalog:catalog@localhost:5470/notifications`),
`KAFKA_BROKERS` (`localhost:9097`), `KAFKA_GROUP` (`notification`), `KAFKA_TOPIC` (`marketplace.orders.v1`),
`ADMIN_TOKEN` (`admin`).

## Тесты

```bash
python -m pytest -q
```

Тесты `tests/test_inbox.py` идут на настоящей PostgreSQL (`notifications_test` из compose, `TEST_DATABASE_URL`):
повторная доставка даёт одно уведомление, спор адресуется продавцу, payload не по контракту и payload без адресата
отклоняются без пометки, `OrderCreated`, собранный из `contracts/orders_v1`, обрабатывается.

## Что почитать

- [Kafka на Python в production](https://vikulin-va.ru/kafka/python/production-essentials/): aiokafka, заголовки, commit offset.
- [Распределённые паттерны на Python](https://vikulin-va.ru/patterns/python/distributed-patterns/): идемпотентный потребитель.
