# Каталог: учебная версия на FastAPI

Каталог маркетплейса, написанный так, как пишут обычный FastAPI-сервис: роутер ->
сервис -> хранилище, модель SQLAlchemy, миграции Alembic, транзакция на операцию.
С этого начинается практикум.

## Запустить

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter redis
python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -e ".[dev]"
uvicorn catalog_starter.main:app --port 8182
```

Сервис поднимется на 8182, схему накатят миграции при старте.

```bash
curl -s localhost:8182/products
curl -s -X POST localhost:8182/products -H 'Content-Type: application/json' \
  -d '{"title":"Беспроводная мышь","price":1990.00,"stock":7}'
curl -s -X POST localhost:8182/products/<id>/reserve -H 'Content-Type: application/json' \
  -d '{"quantity":2}'
```

Настройки - переменные окружения: `HTTP_PORT` (`8182`), `DATABASE_URL`
(база из compose на 5470), `CACHE` (`redis` или `memory`), `REDIS_URL`.

## Прогнать тесты

```bash
pytest
```

Тесты идут на настоящем PostgreSQL - на второй базе того же контейнера
(`catalog_starter_test`, `TEST_DATABASE_URL`). Так они проверяют и SQL,
и блокировки, которых в памяти не увидеть.

## Что внутри

| файл | зачем |
|---|---|
| `catalog_starter/product/model.py` | модель `Product` и единственное бизнес-правило: нельзя зарезервировать больше, чем есть |
| `catalog_starter/product/repository.py` | хранилище на SQLAlchemy и единица работы: одна транзакция на операцию |
| `catalog_starter/product/service.py` | сценарии: найти, создать, зарезервировать |
| `catalog_starter/product/router.py` | REST: `GET /products`, `GET /products/{id}`, `POST /products`, `POST /products/{id}/reserve` |
| `catalog_starter/problem.py` | тело ошибки в формате Problem Details, коды 400, 404 и 409 |
| `migrations/` | миграции Alembic, применяются при старте |

Правило, вокруг которого всё крутится, живёт в модели, а не в сервисе:

```python
def reserve(self, quantity: int) -> None:
    if quantity > self._stock:
        raise OutOfStockError(self._id, quantity, self._stock)
    self._stock -= quantity
```

Атрибуты `Product` закрыты и наружу торчат свойствами только на чтение: менять остаток
снаружи нечем, правило нельзя обойти. Это первый шаг к тому, что дальше в программе
называется доменной моделью.
