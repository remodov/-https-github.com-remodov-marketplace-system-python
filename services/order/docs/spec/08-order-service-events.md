---
type: context-section
context: order-service
parent: "[[order-service]]"
section: events
tier: C
tags:
  - events
  - bc/order
  - kafka
---

## 8. Domain Events

Все события - неизменяемые `dataclass`-ы, наследующие `DomainEvent`. Регистрируются в агрегате `Order` через `register_event(...)` и публикуются через `Outbox` в той же транзакции.

### Внутренние и внешние

- **Внутренние** обрабатываются подписчиками в том же процессе после фиксации транзакции - например, обновление денормализованных Read Model в той же БД.
- **Внешние** публикуются в Kafka через `Outbox-relay`. Это контракт с другими сервисами.

### Каталог

| Событие | Триггер | Тип | Топик Kafka | Подписчики |
|---|---|---|---|---|
| `OrderCreated` | после `CreateOrder` | внутреннее | - | Order Read Model (для `SearchMyOrders`) |
| `OrderConfirmed` | после `ConfirmOrder` | внешнее | `marketplace.orders.v1` | Inventory (резервирует), Notification (welcome SMS) |
| `OrderReservationFailed` | после `HandleReservationFailed` | внешнее | `marketplace.orders.v1` | Notification (сообщение покупателю) |
| `OrderPaid` | после `HandlePaymentSucceeded` | внешнее | `marketplace.orders.v1` | Notification (чек), Inventory (commit резерва), Settlement (учёт) |
| `OrderShipped` | после `MarkShipped` | внешнее | `marketplace.orders.v1` | Notification (трек-номер) |
| `OrderDelivered` | после `MarkDelivered` | внешнее | `marketplace.orders.v1` | Notification (запрос отзыва), внутренний таймер 14 дней |
| `OrderCompleted` | после `CloseDeliveredOrdersJob` | внешнее | `marketplace.orders.v1` | Settlement (выручка) |
| `OrderCancelled` | после `CancelOrder` | внешнее | `marketplace.orders.v1` | Inventory (снять резерв), Notification |
| `OrderExpired` | после `ExpireUnpaidOrdersJob` | внешнее | `marketplace.orders.v1` | Inventory (снять резерв) |
| `DisputeOpened` | после `OpenDispute` | внешнее | `marketplace.orders.v1` | Notification (продавцу), Admin BFF (в очередь споров) |
| `DisputeResolved` | после `ResolveDispute` | внешнее | `marketplace.orders.v1` | Notification |
| `OrderRefunded` | после Saga `ProcessRefund` | внешнее | `marketplace.orders.v1` | Settlement (компенсация), Notification |

### Структура события

Все события наследуют `DomainEvent` и имеют:

- `id: UUID` - id события, генерируется при создании;
- `occurredAt: datetime` - время возникновения;
- `aggregateType: "Order"`;
- `aggregateId: str` - `orderId`.

Плюс типобезопасный payload, специфичный для события.

### Пример: `OrderConfirmed`

```python
@dataclass(frozen=True)
class OrderConfirmed(DomainEvent):
    customer_id: UUID
    seller_id: UUID
    items: tuple[ItemSnapshot, ...]
    total: Money

    @classmethod
    def of(cls, order: "Order") -> "OrderConfirmed":
        return cls(
            aggregate_type="Order",
            aggregate_id=str(order.id),
            customer_id=order.customer_id,
            seller_id=order.seller_id,
            items=tuple(ItemSnapshot.of(item) for item in order.items),
            total=order.total,
        )
```

### Пример: `OrderPaid`

```python
@dataclass(frozen=True)
class OrderPaid(DomainEvent):
    payment_id: UUID
    amount: Money
    paid_at: datetime
```

### Контракты для внешних потребителей

Сериализация - JSON, схема версионирована: `marketplace.orders.v1`. Изменения payload - через minor (добавление optional полей) или новую версию топика (breaking changes). Версия указана в Kafka header `x-event-version`.

См. интеграции: `14-order-service-integrations/order-service-publishes-orderconfirmed.md`, `...-orderpaid.md`, и т.д. - там точные контракты для каждого события.

### Идемпотентность приёма

При приёме событий извне (`PaymentSucceeded`, `ItemReserved`) Order Service использует таблицу `processed_events (event_id PK, processed_at)` и не обрабатывает дубликаты повторно. Реализуется в каждом event handler (`BR-011`).
