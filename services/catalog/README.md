# catalog

Catalog Service из сквозного маркетплейс-кейса сайта [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/case/catalog-service/),
взрослая версия учебного `catalog-starter`: те же карточки товаров, но с границами слоёв, спецификацией,
ролями, владением и журналом действий администратора.

**Уровень 2** методологии Use Case Pattern: команда и обработчик сценария с явными портами, без агрегатов
с событиями и саг. Простой автомат статусов `DRAFT -> PUBLISHED <-> HIDDEN`, владение проверяется в
обработчике сценария, хранение через SQLAlchemy Core с запросами в адаптере.

Спецификация в [`docs/spec/`](docs/spec/), контракт REST в [`docs/catalog.openapi.yaml`](docs/catalog.openapi.yaml).

## Как устроен сервис

```
catalog/main.py                         точка входа для uvicorn
catalog/
  core/
    errors.py                           ошибки с видом и кодом, общие для ядра и адаптеров
    security/                           Principal из токена, роли
    product/
      aggregate/                        Product: поля закрыты, правила в методах
      port/out.py                       протоколы: репозиторий, журнал, часы, идентификаторы, единица работы
      usecase/                          команды: создать, сменить цену, опубликовать, скрыть
      query/                            чтение: карточка, мои товары
  adapter/
    inbound/http/                       FastAPI: роутеры, Problem Details, роли в зависимостях, схемы pydantic
    outbound/persistence/               SQLAlchemy Core, миграции Alembic, сессия в contextvar, журнал
    outbound/system/                    системные часы и uuid
  bootstrap/                            настройки, сборка зависимостей, создание приложения
migrations/                             Alembic: products, catalog_audit_log
tests/                                  архитектурный, жизненный цикл, смена цены
```

Правило одно: `catalog/core` импортирует только стандартную библиотеку и свои модули. Его стережёт
`tests/test_architecture.py`: разбирает импорты файлов ядра через `ast` и падает на `fastapi`, `sqlalchemy`,
`pydantic` и прочих технологиях. Там же `isinstance(..., ProductRepository)` по `runtime_checkable`-протоколу
ловит расхождение порта и реализации.

## Запуск

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter
python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -e ".[dev]"
uvicorn catalog.main:app --port 8180
```

Переменные: `HTTP_PORT` (`8180`), `DATABASE_URL` (`postgresql+asyncpg://catalog:catalog@localhost:5470/catalog`),
`AUTH_MODE` (`local` или `jwt`), для `jwt` ещё `JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`.

В режиме `local` токен это строка `role.uuid`, роли `seller`, `admin`, `customer`:

```bash
SELLER=$(uuidgen | tr A-Z a-z)
curl -s -X POST localhost:8180/api/v1/products -H "Authorization: Bearer seller.$SELLER" \
  -H 'Content-Type: application/json' -d '{"title":"Кофемолка","price":2490.5,"currency":"RUB"}'
```

Карточку в статусе `DRAFT` видят только владелец и администратор; опубликованную видят все без токена.

## Тесты

```bash
python -m pytest -q
```

Интеграционные тесты идут на настоящей PostgreSQL (`catalog_test` из compose, `TEST_DATABASE_URL`):
приложение поднимается через lifespan и накатывает миграции, каждый тест чистит таблицы.
Архитектурные тесты проверяют направление импортов.

## Коды ошибок

`VALIDATION_ERROR`, `MALFORMED_REQUEST`, `INVALID_PRICE`, `INVALID_CURRENCY`, `PRODUCT_NOT_FOUND`,
`OWN_PRODUCT_REQUIRED` (чужой товар, 404, а не 403), `INVALID_STATE_TRANSITION` (409), `TOKEN_MISSING` (401),
`TOKEN_INVALID` (401), `ACCESS_DENIED` (403). Тело ошибки в формате Problem Details, `type` вида `urn:problem:catalog:<CODE>`.

## Что почитать

- [Catalog Service в кейсе](https://vikulin-va.ru/use-case-pattern/case/catalog-service/) и [Use Case Pattern](https://vikulin-va.ru/use-case-pattern/).
- [Гексагональная архитектура на Python](https://vikulin-va.ru/patterns/hexagonal/python/core-layer/): почему ядро не знает про FastAPI и SQLAlchemy.
- [Архитектурные тесты на Python](https://vikulin-va.ru/patterns/hexagonal/python/architecture-tests/).
- [ABAC и владение ресурсом в Python](https://vikulin-va.ru/patterns/auth-patterns/python/abac-resource-ownership/).
- Учебная версия того же сервиса для первых шагов практикума: `../catalog-starter`.
