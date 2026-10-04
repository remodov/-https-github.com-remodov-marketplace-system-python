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
(база из compose на 5470), `CACHE` (`redis` или `memory`), `REDIS_URL`, `SERVICE_NAME`
(`catalog-starter`, метка `service` в метриках и `service.name` в трассах),
`OTEL_EXPORTER_OTLP_ENDPOINT` (адрес коллектора; пустой - трассы не отправляются),
`TRACE_SAMPLE_RATIO` (доля трасс от 0 до 1, по умолчанию `1.0`).

Пробы и метрики: `GET /health/live` отвечает 204, пока процесс жив; `GET /health/ready` отвечает 204,
если база отвечает на `SELECT 1`, иначе 503 с кодом `NOT_READY`; `GET /metrics` отдаёт гистограмму
`http_server_request_duration_seconds` в формате Prometheus с метками `service`, `method`, `route`
(шаблон маршрута, не сырой URL) и `status`.

## Собрать образ

Контекст сборки - корень репозитория, образ собирается в две стадии: первая ставит зависимости из
`pyproject.toml` в `/opt/venv` (`pip install --only-deps`, без кэша), вторая берёт из неё только
окружение и код сервиса и бежит от пользователя `app` (uid 65532), без pip-кэша и компиляторов.

```bash
cd ../..
docker build -f services/catalog-starter/Dockerfile -t catalog-starter-python:0.1.0 .
docker run --rm -p 8182:8182 \
  -e DATABASE_URL=postgresql+asyncpg://catalog:catalog@host.docker.internal:5470/catalog_starter \
  -e REDIS_URL=redis://host.docker.internal:6383 \
  catalog-starter-python:0.1.0
curl -i localhost:8182/health/ready
```

База стенда видна из контейнера как `host.docker.internal`; на Linux без Docker Desktop подойдёт
`--network host` и `localhost:5470`. Манифест для Kubernetes с пробами, лимитами и `preStop` -
`deploy/k8s/catalog-starter.yaml`, проверка выката - `python3 tools/check-deploy.py` из корня.

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
| `catalog_starter/observability.py` | пробы `/health/live` и `/health/ready`, `/metrics` для Prometheus, middleware времени ответа, сэмплер и экспорт трасс в OTLP |
| `migrations/` | миграции Alembic, применяются при старте |
| `Dockerfile` | образ в две стадии: зависимости в `/opt/venv`, рантайм без компиляторов и root |

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
