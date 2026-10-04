# contracts

Внешний контракт событий заказа: один на продюсера (`services/order`) и потребителей
(`services/notification`, позже `services/payment`).

- [`asyncapi/marketplace-orders-v1.yaml`](asyncapi/marketplace-orders-v1.yaml) - канал, заголовки, сообщения.
- [`schemas/order-events.yaml`](schemas/order-events.yaml) - поля событий, один источник правды.
- [`orders_v1`](orders_v1/orders_v1/events.py) - пакет `marketplace-contracts-orders-v1` с теми же полями в виде
  pydantic-моделей: продюсер собирает payload из него, потребитель читает в него, оба валидируются против одних типов.

Пакет ставится в общее окружение репозитория:

```bash
pip install -e contracts/orders_v1
```

Контракт намеренно плоский: во внешнее событие не протекают внутренние типы сервиса. `customerId` - строка
с UUID, а не вложенный объект; сумма - десятичная строка, а не число с плавающей точкой. Модели строгие:
`itemsCount` строкой или `totalAmount` числом не пройдут валидацию ни у продюсера, ни у потребителя.
