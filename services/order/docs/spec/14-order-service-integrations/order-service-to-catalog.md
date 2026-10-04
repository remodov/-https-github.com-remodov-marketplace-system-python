---
type: integration
integration-type: inner
source: "[[order-service]]"
target: "[[catalog-service]]"
direction: outbound
protocol: rest
sync: sync
ddd-pattern:
  - conformist
tags:
  - integration
  - integration/inner
  - protocol/rest
  - sync/sync
  - ddd/conformist
---

# Order Service -> Catalog Service (REST, sync)

Order Service вызывает Catalog для получения актуальной цены и факта существования товара при создании черновика заказа и применении промокода.

## Контракт

- **Endpoints (на стороне Catalog):**
  - `GET /api/v1/products/{id}` - получить товар, цену, остаток (read-only).
  - `POST /api/v1/promos/{code}/validate` - валидация промокода (применим ли к корзине, не истёк, есть применения).
- **OpenAPI:** `catalog-service/docs/api/catalog.openapi.yaml`.
- **DDD-паттерн:** Conformist. Order соответствует контракту Catalog без переговоров.

## Аутентификация

Service-to-service: Order использует mTLS-сертификат + JWT с ролью `system`, scope `catalog:read`.

## Resilience

- **Timeout:** 500 мс на соединение, 1 секунда на запрос товара.
- **Retry:** 2 попытки с паузой 50 мс; повторяются только сетевые ошибки и 5xx.
- **Circuit Breaker:** на Catalog (собственный размыкатель в адаптере). Пять сорванных вызовов подряд открывают его на 60 секунд, потом одна пробная попытка; `PRODUCT_NOT_FOUND` отказом не считается.
- **Fallback при открытом CB:** для `GetProduct` - возврат `503 SERVICE_DEGRADED` пользователю; для валидации промокода - пропуск (промокод не применяется).

## SLA

`< 200ms p95` от Catalog. Если выше - открывается алёрт, переключаемся на read-replica (внутри Catalog).
