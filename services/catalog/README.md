# catalog

Catalog Service из сквозного маркетплейс-кейса сайта [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/case/catalog-service/),
взрослая версия учебного `catalog-starter`: те же карточки товаров, но с границами слоёв, спецификацией,
ролями, владением, журналом действий администратора и подписанными ссылками на загрузку фото.

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
      port/out.py                       протоколы: репозиторий, журнал, часы, идентификаторы, единица работы, хранилище файлов
      usecase/                          команды: создать, сменить цену, опубликовать, скрыть, выдать ссылку на загрузку фото
      query/                            чтение: карточка, мои товары, витрина опубликованных
  adapter/
    inbound/http/                       FastAPI: роутеры, Problem Details, роли в зависимостях, схемы pydantic
    outbound/persistence/               SQLAlchemy Core, миграции Alembic, сессия в contextvar, журнал
    outbound/system/                    системные часы и uuid
    outbound/storage/                   boto3: подпись ссылки на PUT объекта в S3-совместимое хранилище
  bootstrap/                            настройки, сборка зависимостей, создание приложения
migrations/                             Alembic: products, catalog_audit_log
tests/                                  архитектурный, жизненный цикл, смена цены, ссылка на загрузку фото, витрина
```

Правило одно: `catalog/core` импортирует только стандартную библиотеку и свои модули. Его стережёт
`tests/test_architecture.py`: разбирает импорты файлов ядра через `ast` и падает на `fastapi`, `sqlalchemy`,
`pydantic` и прочих технологиях. Там же `isinstance(..., ProductRepository)` по `runtime_checkable`-протоколу
ловит расхождение порта и реализации.

## Запуск

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter minio minio-init
python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -e ".[dev]"
uvicorn catalog.main:app --port 8180
```

Переменные: `HTTP_PORT` (`8180`), `DATABASE_URL` (`postgresql+asyncpg://catalog:catalog@localhost:5470/catalog`),
`AUTH_MODE` (`local` или `jwt`), для `jwt` ещё `JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`.
Хранилище картинок: `S3_ENDPOINT` (`http://localhost:9004`), `S3_BUCKET` (`marketplace-images`),
`S3_ACCESS_KEY` и `S3_SECRET_KEY` (`marketplace`), `S3_REGION` (`us-east-1`), `IMAGE_UPLOAD_URL_TTL_SECONDS` (`600`).

В режиме `local` токен это строка `role.uuid`, роли `seller`, `admin`, `customer`:

```bash
SELLER=$(uuidgen | tr A-Z a-z)
curl -s -X POST localhost:8180/api/v1/products -H "Authorization: Bearer seller.$SELLER" \
  -H 'Content-Type: application/json' -d '{"title":"Кофемолка","price":2490.5,"currency":"RUB"}'
```

Карточку в статусе `DRAFT` видят только владелец и администратор; опубликованную видят все без токена.
Витрина `GET /api/v1/products` тоже без токена: страница опубликованных карточек всех продавцов с той же
пагинацией и сортировкой, что у «моих товаров»; черновики и скрытые в неё не попадают. Ею пользуется
веб-клиент `web/` из четырнадцатого шага.

## Загрузка фото

Фото грузится мимо сервиса: владелец просит временную ссылку, а файл кладёт браузер прямо в хранилище.
Сервис решает только, кому выдать ссылку: чужой товар для не-владельца выглядит как несуществующий.

```bash
curl -s -X POST localhost:8180/api/v1/products/$PRODUCT/image-upload-url -H "Authorization: Bearer seller.$SELLER" \
  -H 'Content-Type: application/json' -d '{"contentType":"image/jpeg"}'
curl -X PUT "$URL_ИЗ_ОТВЕТА" -H 'Content-Type: image/jpeg' --data-binary @photo.jpg
```

Подпись считает `boto3` локально по ключам из настроек (`generate_presigned_url("put_object", ...)`, подпись
`s3v4`, адресация `path`, чтобы ссылка смотрела на `localhost:9004/marketplace-images/...`, а не на поддомен).
В сеть при подписи сервис не ходит, поэтому для тестов MinIO не нужен. `Content-Type` входит в подпись:
`PUT` с другим типом хранилище отвергнет с `SignatureDoesNotMatch`; ссылка живёт `IMAGE_UPLOAD_URL_TTL_SECONDS`.

Проверить, что файл лёг: консоль MinIO на `http://localhost:9005` (логин и пароль `marketplace`), корзина
`marketplace-images`, папка `products/<id>/`; или из контейнера:

```bash
docker exec mppy-minio sh -c 'mc alias set local http://localhost:9000 marketplace marketplace >/dev/null && mc ls --recursive local/marketplace-images'
```

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
- [Проверка JWT в Python](https://vikulin-va.ru/patterns/auth-patterns/python/jwt-validation/) и [роли Keycloak](https://vikulin-va.ru/keycloak/python/roles-and-access/).
- [S3 из Python через boto3](https://vikulin-va.ru/object-storage/python/boto3-s3/) и [выходные адаптеры](https://vikulin-va.ru/patterns/hexagonal/python/adapters-out/).
- Учебная версия того же сервиса для первых шагов практикума: `../catalog-starter`.
