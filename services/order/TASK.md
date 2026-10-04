# Шаг 10. Событие: outbox и внешний контракт

## Что нужно сделать

Заказ создан, и об этом должны узнать соседи: уведомления шлёт `notification`,
платёжное намерение потом создаст `payment`. Отправить событие прямо из кода
нельзя: если запись в базу прошла, а отправка в Kafka упала, событие потеряно
навсегда; если наоборот, соседи узнают о заказе, которого нет.

Отсюда outbox: событие пишется **в ту же транзакцию**, что и заказ, обычной
строкой в таблицу. Дальше отдельная фоновая задача (relay) забирает
неотправленные строки и публикует их. Падение между записью и отправкой ничего
не теряет: строка осталась, relay заберёт её на следующем круге.

Вторая половина шага - **что именно** уезжает в этой строке.

## Задачи

1. **Запись в outbox.** `SqlAlchemyOutbox.append` кладёт каждое событие
   строкой: идентификатор, агрегат, тип, версия, payload, время.
   `published_at` остаётся пустым - это признак «ещё не отправлено». Строка
   должна лечь в ту же сессию, что и заказ: внутри `async with uow.begin()`
   её даёт `session_in_scope`, своей транзакции открывать нельзя.
2. **Внешний контракт.** Payload это договор с чужими сервисами, а не дамп
   внутреннего класса. `payload_of` собирает `OrderCreatedPayload` из пакета
   `contracts/orders_v1`: `customerId` и `sellerId` строками UUID, сумма
   десятичной строкой, `itemsCount` числом - и ничего сверх контракта.
   Байты даёт `payload.encode()`, в колонку `jsonb` их кладёт `jsonb_of`.
3. **Relay.** `OutboxRelay.once` в одной единице работы берёт пачку
   неотправленных строк, публикует каждую через порт `ExternalEventPublisher`
   и помечает отправленной. Если брокер отказал, транзакция откатывается
   целиком и строки остаются; наружу уходит `PublishFailed`. Цикл `run` и
   остановка `stop` уже есть.

## Где править

`# TODO шаг 10`:

- `order/adapter/outbound/persistence/outbox_repository.py` - `append` и
  `payload_of`;
- `order/core/order/usecase/relay_outbox.py` - `once`.

Протокол `EventOutbox` (`append`, `unpublished`, `mark_published`) и протокол
`ExternalEventPublisher` уже описаны в `order/core/order/port/out.py`.
`unpublished` и `mark_published` реализованы, издатель на aiokafka лежит в
`order/adapter/outbound/kafka/publisher.py`, издатель в лог - в
`order/adapter/outbound/system/log_publisher.py`.

## Как проверить себя

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter kafka
pip install -e ../../contracts/orders_v1 -e ".[dev]"
python -m pytest -q
```

Красные `test_outbox_*` в `tests/test_outbox.py`: строка рождается вместе с
заказом (`test_outbox_order_created_is_written_with_the_order`), поля payload
ровно по контракту (`test_outbox_payload_follows_external_contract`), повтор
запроса не рождает второе событие
(`test_outbox_nothing_leaks_when_the_transaction_rolls_back`), relay публикует
и помечает (`test_outbox_relay_publishes_and_marks_rows`), при лежащем брокере
строка остаётся (`test_outbox_relay_keeps_row_when_broker_fails`).
`test_kafka_publisher_delivers_payload_with_headers` в
`tests/test_kafka_publisher.py` проверяет издателя на настоящей Kafka со стенда
и зелёный с самого начала.

Потом сквозной прогон: подними `catalog` (8180), `order` (8181) и
`notification` (8185), создай заказ с токеном покупателя и `Idempotency-Key`
и спроси `notification` список уведомлений покупателя с
`Authorization: Bearer admin`. Порядок команд - в `README.md`, раздел
«Сквозной прогон».

## На что посмотреть по дороге

- Эта грабля настоящая, а не выдуманная: в Java-версии `customerId` уезжал в
  Kafka вложенным объектом `{"value": "..."}`, потребитель читал его строкой и
  падал, адресат уведомления не определялся вовсе. На Python та же грабля
  выглядит как `json.dumps(asdict(event), default=str)` внутреннего
  dataclass: ключи в snake_case (`customer_id` вместо `customerId`), `Money`
  объектом `{"amount": ..., "currency": ...}`, список позиций и поле `at`,
  которых в контракте нет. Тест
  `test_process_payload_off_contract_is_rejected_without_marking` в
  `notification` показывает, что потребитель с таким payload делает.
- Почему нельзя просто отдать наружу свой класс: внутренний класс свободно
  меняют при рефакторинге, а контракт менять нельзя, на нём висят чужие
  сервисы. Контракт лежит в `contracts/` в формате AsyncAPI, посмотри, как там
  описан `OrderCreatedPayload`, и сравни с pydantic-моделью в
  `contracts/orders_v1/orders_v1/events.py`: она строгая, `itemsCount`
  строкой или `totalAmount` числом не пройдут.
- Relay помечает строку отправленной **после** успешной публикации. Что будет,
  если пометить до? А если Kafka приняла, но пометка не записалась?
- Из предыдущего вопроса растёт правило для потребителя: доставка бывает
  повторной, и второе письмо покупателю слать нельзя. Как `notification` это
  ловит? Посмотри `notification/inbox.py`.
- `FOR UPDATE SKIP LOCKED` в `unpublished` (`with_for_update(skip_locked=True)`):
  два экземпляра сервиса заказов не возьмут одну строку дважды. А что будет без
  `SKIP LOCKED`?
- Грабли aiokafka: клиент требует запущенный цикл событий уже в конструкторе,
  поэтому продюсер создаётся в `start()` внутри lifespan, а не при импорте;
  заголовки - список кортежей `(str, bytes)`, значения кодируются и
  декодируются руками; потребитель с `enable_auto_commit=False` фиксирует
  offset сам и только после того, как транзакция обработки закоммичена.

## Материал

- Kafka на Python с нуля: https://vikulin-va.ru/kafka/python/fundamentals/
- Распределённые паттерны на Python, outbox и идемпотентный потребитель: https://vikulin-va.ru/patterns/python/distributed-patterns/
- asyncio-задачи и outbox-relay при остановке: https://vikulin-va.ru/graceful-shutdown/python/scheduled-async-outbox/
- Kafka на Python в production, заголовки и commit offset: https://vikulin-va.ru/kafka/python/production-essentials/
