# Веб-клиент маркетплейса

Витрина, корзина, оформление и статус заказа поверх BFF. Приложение нарочно
маленькое: смысл не в вёрстке, а в двух вещах, которые обычно делают позже
и криво.

**Первое.** Клиент ходит в одну ручку экрана, а не в три сервиса: `/api/v1/screens/order/{id}`.
**Второе.** Приложение считает воронку: сколько людей увидело карточку, сколько
положило в корзину, сколько начало оформление, сколько оплатило. Без этих чисел
разговор о продукте превращается в спор о вкусах.

Клиент одинаков для всех языков практикума: это React, TypeScript и Vite, бэкенд ему
безразличен. От Go- и Java-версий отличаются только порты сервисов в `vite.config.ts`.

## Запустить

Нужен Node.js 20 или новее.

```bash
npm install
npm run dev
```

В разработке Vite сам играет роль шлюза: `/api/v1/products` уходит в каталог (8180),
`/api/v1/orders` в заказы (8181), `/api/v1/screens` в BFF (8190). Для сборки адрес API
задаётся переменной `VITE_API_URL`. Токен покупателя для стенда в режиме `AUTH_MODE=local`
берётся из `VITE_CUSTOMER_TOKEN` (по умолчанию `customer.00000000-0000-0000-0000-000000000001`).

Стенд целиком: `docker compose -f ../infra/compose.yaml up -d`, затем из одного окружения
(см. [корневой README](../README.md)) четыре сервиса, каждый из своей папки:

```bash
uvicorn catalog.main:app --port 8180
uvicorn order.main:app --port 8181
uvicorn payment.main:app --port 8186
uvicorn bff.main:app --port 8190
```

Товар на витрине появляется после публикации продавцом (`POST /api/v1/products/{id}/publish`);
витрину отдаёт каталог без токена ручкой `GET /api/v1/products`.

## Тесты

```bash
npm test
```

Сеть подменяется заглушкой, браузер не нужен.

## Что внутри

| файл | зачем |
|---|---|
| `src/funnel/funnel.ts` | шаги воронки, отправка событий и расчёт конверсии |
| `src/api/marketplace.ts` | походы в каталог, заказы и BFF, включая `Idempotency-Key` при создании заказа |
| `src/components/Shop.tsx` | каталог, корзина, оформление, статус |

## Сквозной прогон

Стенд поднят, четыре сервиса запущены, `npm run dev` открыл клиент на `http://localhost:5173`.
Продавец заводит и публикует товар прямо в каталоге, витрину смотрим через прокси Vite:

```bash
SELLER=$(uuidgen | tr A-Z a-z)
PRODUCT=$(curl -s -X POST localhost:8180/api/v1/products -H "Authorization: Bearer seller.$SELLER" \
  -H 'Content-Type: application/json' -d '{"title":"Кофемолка","price":2490.5,"currency":"RUB"}' | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
curl -s -o /dev/null -X POST localhost:8180/api/v1/products/$PRODUCT/publish -H "Authorization: Bearer seller.$SELLER"
curl -s localhost:5173/api/v1/products
```

Что получается: `GET /api/v1/products` на порту клиента уходит в каталог и возвращает страницу
опубликованных карточек с «Кофемолкой» и её `sellerId`; черновик соседнего продавца в выдаче не виден.
В браузере карточка появляется в каталоге, «В корзину» наращивает счётчик, «Оформить» отправляет
`POST /api/v1/orders` с `Idempotency-Key` и токеном покупателя (повтор с тем же ключом возвращает тот же
`id`), затем `GET /api/v1/screens/order/{id}` через BFF: `Заказ DRAFT`, `Оплата: NONE`, строка
«Кофемолка × 1», итого `2490.5`. Последний шаг воронки `order_paid` при этом не отмечается: клиент
смотрит на `paymentStatus` экрана, а не на нажатие кнопки. После подтверждения заказа, авторизации и
списания платежа (`README.md` сервиса `payment`) тот же экран отвечает `status: PAID`,
`paymentStatus: CAPTURED`.

Тот же путь без браузера: модуль `src/api/marketplace.ts` импортируется из Node 24 напрямую (типы
отбрасываются при загрузке), достаточно подменить `fetch` так, чтобы относительные пути уходили на
`http://localhost:5173`, и вызвать `loadCatalog`, `createOrder`, `loadOrderScreen`.

## Что почитать

- [Frontend](https://vikulin-va.ru/frontend/): React и TypeScript по делу.
- [Продукт-инженер](https://vikulin-va.ru/product-engineer/): зачем разработчику продуктовые числа.
- [Тестирование](https://vikulin-va.ru/testing/): что проверять на клиенте.
