---
type: context-section
context: order-service
parent: "[[order-service]]"
section: queries
tier: C
tags:
  - queries
  - read-model
  - cqrs
  - bc/order
---

## 9. Queries / Read Model

Чтения отделены от записи: запрос - `dataclass`, обработчик читает Read Model. Read Model - собственный набор таблиц, обновляемых по событиям.

### Запросы

| Класс | URL | Параметры | Возвращает | Роли | ABAC |
|---|---|---|---|---|---|
| `GetOrderByIdQuery` | `GET /api/v1/orders/{id}` | `id` | `OrderResponse` | customer / seller / admin | владение или admin |
| `SearchMyOrdersQuery` | `GET /api/v1/orders?role=customer&status=...&page=...` | `status?`, `dateFrom?`, `dateTo?`, `page`, `size` | `Page[OrderSummary]` | customer | `customerId == jwt.sub` |
| `SearchSellerOrdersQuery` | `GET /api/v1/orders?role=seller&status=...` | `status?`, `dateFrom?`, `dateTo?`, `page`, `size` | `Page[OrderSummary]` | seller | `sellerId == jwt.sub` (через JOIN с items) |
| `SearchAllOrdersQuery` | `GET /api/v1/orders?role=admin&...` | расширенные фильтры | `Page[OrderSummary]` | admin | - |
| `GetOrderTimelineQuery` | `GET /api/v1/orders/{id}/timeline` | `id` | `list[TimelineEntry]` | customer / seller / admin | владение или admin |

Все обработчики чтения работают в транзакции только на чтение; `SearchSellerOrdersQuery` дополнительно кэшируется в Redis на 30 секунд.

### Read Model

#### Таблица `order_summaries`

Денормализованная плоская таблица для списков заказов.

| Колонка | Тип | Назначение |
|---|---|---|
| order_id | UUID PK | |
| customer_id | UUID | для индекса `(customer_id, status)` |
| primary_seller_id | UUID | первый seller в заказе (для индекса `(seller_id, status)`) |
| status | order_status | enum |
| total_amount | numeric | для сортировки/фильтрации по сумме |
| currency | varchar(3) | RUB |
| items_count | int | для UI |
| first_product_title | varchar | превью в списке |
| created_at, updated_at | timestamp | |

Индексы:
- `idx_summaries_customer (customer_id, status, created_at DESC)`
- `idx_summaries_seller (primary_seller_id, status, created_at DESC)`
- `idx_summaries_status_created (status, created_at)` - для admin-поиска

Обновляется подписчиком после фиксации транзакции на события `OrderCreated`, `OrderPaid`, `OrderShipped`, `OrderDelivered`, `OrderCompleted`, `OrderCancelled`, `OrderRefunded`.

#### Таблица `order_timelines`

История переходов состояний для UI «история заказа».

| Колонка | Тип | Назначение |
|---|---|---|
| id | UUID PK | |
| order_id | UUID FK | |
| event_type | varchar | `OrderCreated`, `OrderPaid`, ... |
| occurred_at | timestamp | |
| actor_type | varchar | `customer` / `seller` / `system` / `admin` |
| actor_id | UUID? | |
| metadata | jsonb | дополнительные поля события |

Индекс `idx_timeline_order_time (order_id, occurred_at)`.

### Согласованность

Read Model **eventual consistent** относительно write-side (Outbox-relay вносит лаг). Типичный лаг - < 1 секунды. UI явно предупреждает: «изменения отображаются с задержкой до 5 секунд».

В critical-path операциях (например, кнопка «оплатить» сразу после создания) - клиент использует **read-your-own-writes**: Customer BFF после создания заказа сразу делает `GetOrderById` через **write-side** (запрос идёт к основному `orders` таблице, не к `order_summaries`).
