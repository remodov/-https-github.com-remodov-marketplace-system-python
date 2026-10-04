# Маркетплейс на Python: сквозная система для практики

Та же система, что в [практикуме на Java](https://github.com/remodov/marketplace-system) и
[на Go](https://github.com/remodov/marketplace-system-go): маркетплейс из разбора
[«Как разбить систему на сервисы»](https://vikulin-va.ru/use-case-pattern/case/services-map/),
только написанный на Python, FastAPI и SQLAlchemy. Репозиторий - практическая часть программы
[«Backend · Python»](https://vikulin-va.ru/programs/backend-python/) с
[vikulin-va.ru](https://vikulin-va.ru/): каждый шаг практикума привязан к статьям,
которые закрывают его тему.

## Что внутри

| сервис | отвечает за | стек |
|---|---|---|
| `services/catalog-starter` | карточки товаров, остатки, резерв, поиск | FastAPI, SQLAlchemy 2 (async), Alembic, Redis |
| `services/catalog` | те же карточки по-взрослому: слои, спецификация, роли, владение, журнал администратора | FastAPI, SQLAlchemy 2 Core (async), Alembic, PyJWT, архитектурные тесты |
| `services/order` | оформление заказов: агрегат `Order`, цены из каталога, клиент с таймаутами, повтором и размыкателем, идемпотентность, outbox, статусная модель и сага отмены | FastAPI, SQLAlchemy 2 Core (async), Alembic, httpx, PyJWT, aiokafka |
| `services/payment` | платежи: автомат статусов, одна авторизация на заказ, безопасный повторный возврат | FastAPI, asyncpg |
| `services/notification` | уведомления: потребитель событий заказа с защитой от повторной доставки | FastAPI, SQLAlchemy 2 Core (async), Alembic, aiokafka |
| `contracts` | внешние контракты событий заказа и платежа: AsyncAPI, схемы и pydantic-пакеты для продюсера и потребителей | AsyncAPI 3, pydantic |

Дальше по плану появляются `services/bff` и `web` - по образцу Java- и Go-версий
([план](docs/practicum/PLAN.md)).

## С чего начинать

[`services/catalog-starter`](services/catalog-starter/README.md): роутер -> сервис ->
хранилище, одна таблица, запросы через SQLAlchemy там, где они читаются, и явный SQL в
миграциях. Клонировал, поднял базу, запустил, увидел товар.

Нужны Python 3.12 или новее и Docker.

```bash
git clone git@github.com:remodov/marketplace-system-python.git
cd marketplace-system-python
docker compose -f infra/compose.yaml up -d postgres-catalog-starter redis
python3 -m venv .venv && source .venv/bin/activate
pip install -e "services/catalog-starter[dev]"
cd services/catalog-starter
pytest
uvicorn catalog_starter.main:app --port 8182
```

Взрослая версия каталога из второй части ставится рядом в то же окружение:

```bash
pip install -e "services/catalog[dev]"
cd services/catalog
python -m pytest -q
uvicorn catalog.main:app --port 8180
```

Сервис заказов из восьмого шага ставится так же и ходит в каталог на `8180`; с десятого шага ему нужны
пакеты контрактов событий из `contracts/`:

```bash
pip install -e contracts/orders_v1 -e contracts/payments_v1 -e "services/order[dev]"
cd services/order
python -m pytest -q
uvicorn order.main:app --port 8181
```

Сервис уведомлений из десятого шага читает события заказа из Kafka:

```bash
pip install -e "services/notification[dev]"
cd services/notification
python -m pytest -q
uvicorn notification.main:app --port 8185
```

Сервис платежей из одиннадцатого шага, в который ходит сага отмены заказа:

```bash
pip install -e "services/payment[dev]"
cd services/payment
python -m pytest -q
uvicorn payment.main:app --port 8186
```

## Поднять стенд

```bash
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml ps
```

| что | порт | зачем |
|---|---|---|
| PostgreSQL | 5470 | базы `catalog_starter`, `catalog`, `orders`, `notifications` и `payments` плюс тестовые `*_test` |
| Redis | 6383 | кэш карточек, шаг 6 |
| Kafka | 9097 | события заказа из outbox, шаг 10; события платежа, шаг 11 |
| MinIO | 9004, 9005 | изображения товаров, шаг 12 |

Порты сдвинуты относительно Java-, Go- и Node-версий, чтобы стенды могли жить на одной машине.

## Как устроен шаг

Ветка `step-NN-<тема>` - задание: каркас на месте, реализация вынута, тест красный,
условие в `TASK.md` внутри сервиса. Ветка `step-NN-<тема>-solution` - эталон.
`main` - накопленный эталон всех шагов.

```bash
git switch step-02-read-endpoint
cd services/catalog-starter && pytest
```

## Что почитать рядом

- [Ядро FastAPI](https://vikulin-va.ru/fastapi/app-structure-and-config/) - структура приложения, зависимости и настройки.
- [SQLAlchemy и ORM](https://vikulin-va.ru/sqlalchemy/orm-and-sqlalchemy/) - сессии, транзакции и миграции Alembic.
- [Use Case Pattern](https://vikulin-va.ru/use-case-pattern/) - как устроены взрослые сервисы второй части.
