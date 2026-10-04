---
type: context-section
context: order-service
parent: "[[order-service]]"
section: stack
tier: C
ucp-level: 3
tags:
  - stack
  - tech/python
  - tech/fastapi
  - tech/sqlalchemy
  - tech/postgres
  - tech/kafka
  - tech/redis
  - tech/ddd
  - bc/order
---

## 17. Стек технологий

### Платформа

- **Python 3.12+** - asyncio, `dataclasses`, `decimal`, `contextvars`.
- **FastAPI** и **uvicorn** - маршрутизация, зависимости, схемы pydantic на границе.

### Use Case Pattern

- Команда - неизменяемый `dataclass`, обработчик - класс с методом `handle(cmd)`; порты - протоколы в `core/order/port/out.py`.
- Запросы отделены от команд пакетом `core/order/query`.

### DDD

- Агрегат `Order` с закрытыми полями и правилами в методах, позиции `Item` внутри агрегата, `Money` и `Address` значениями (`dataclass(frozen=True)`).

### Хранилище

- **PostgreSQL 16+** - основное хранилище (write-side, Outbox, идемпотентные ключи).
- **SQLAlchemy 2 Core (async)** и **asyncpg** - запросы руками в адаптере, сессия транзакции в `contextvars`.
- **Alembic** - миграции, накатываются при старте приложения.

### События

- **Apache Kafka 3.x** - транспорт между сервисами.
- **aiokafka** - продюсер и консьюмер.
- **Outbox-relay** - своя фоновая задача с `SELECT ... FOR UPDATE SKIP LOCKED`.

### Устойчивость

- **httpx.AsyncClient** с `httpx.Timeout` - отдельные таймауты на соединение и на чтение.
- Повтор с паузой - свой цикл на `asyncio.sleep`, только для сетевых ошибок и 5xx.
- Размыкатель - собственный класс в адаптере каталога: порог сорванных вызовов подряд, окно открытого состояния, полуоткрытая проба.

### Безопасность

- **PyJWT** с JWKS - проверка JWT по ключам Keycloak; роли из `realm_access.roles`.
- Локальный режим `AUTH_MODE=local` - токен вида `role.uuid` для тестов и стенда.

### Наблюдаемость

- **logging** - структурные логи JSON.
- **OpenTelemetry** - метрики и трассировка (добавляются на шаге про наблюдаемость).

### Тесты

- **pytest** и **httpx** против ASGI - интеграционные тесты на настоящей PostgreSQL, соседние сервисы подменяются локальным HTTP-сервером на `asyncio.start_server`.
- **ast** - архитектурные тесты на направление импортов.

### Инфраструктура

- **Docker Compose** - стенд в `infra/compose.yaml`.
- **Kubernetes** - деплой на шаге про инфраструктуру.
