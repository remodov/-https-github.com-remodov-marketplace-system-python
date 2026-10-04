# Практикум на Python: маркетплейс по шагам

Сквозная практика к программе «Backend · Python». Вход - знаешь Python, писал обработчики,
про архитектуру пока читал. Система та же, что в Java- и Go-версиях практикума:
маркетплейс из разбора [«Как разбить систему на сервисы»](https://vikulin-va.ru/use-case-pattern/case/services-map/).

Ученик не пишет систему с нуля: каркас, конфигурация и тесты даются. Он реализует
то, ради чего шаг придуман, и проверяет себя зелёным тестом, а не кнопкой
«показать решение».

## Как устроен шаг

Ветка `step-NN-<тема>` - задание: каркас на месте, реализация вынута, тест красный.
`TASK.md` в корне сервиса - условие: что сделать, где стоят `TODO`, чем проверяется,
куда смотреть по дороге. Ветка `step-NN-<тема>-solution` - эталон.

# Часть первая: обычный сервис

## Шаг 1. Запустить каталог и разобрать по частям

**Материал:** [/fastapi/app-structure-and-config/](https://vikulin-va.ru/fastapi/app-structure-and-config/) · [/fastapi/routing-and-requests/](https://vikulin-va.ru/fastapi/routing-and-requests/) · [/fastapi/dependency-injection/](https://vikulin-va.ru/fastapi/dependency-injection/)

**Даётся:** рабочий `catalog-starter`, база в compose, пять зелёных тестов.

**Ученик:** поднимает базу, запускает сервис, дёргает четыре ручки; отвечает, что
делает каждый слой и почему тесты идут на настоящей базе.

**Проверка:** `pytest` зелёный, `curl` возвращает созданный товар.

## Шаг 2. Новая ручка на чтение

**Материал:** [/rest-api/python/query-params/](https://vikulin-va.ru/rest-api/python/query-params/) · [/fastapi/persistence-sqlalchemy/](https://vikulin-va.ru/fastapi/persistence-sqlalchemy/) · [/sqlalchemy/queries/](https://vikulin-va.ru/sqlalchemy/queries/)

**Даётся:** красный тест на `GET /products?maxPrice=…`.

**Ученик:** метод хранилища с запросом, метод сервиса, параметр в роутере.

**Проверка:** тест зеленеет; в логе видно, какой SQL ушёл в базу (`SQL_ECHO=1`).

## Шаг 3. Команда, валидация и коды ошибок

**Материал:** [/fastapi/pydantic-validation/](https://vikulin-va.ru/fastapi/pydantic-validation/) · [/fastapi/middleware-and-errors/](https://vikulin-va.ru/fastapi/middleware-and-errors/) · [/rest-api/python/errors/](https://vikulin-va.ru/rest-api/python/errors/)

**Даётся:** тесты на 400, 404 и 409; обработчики исключений, которые переводят ошибки в Problem Details, как образец.

**Ученик:** изменение цены и остатка: проверки входа в моделях Pydantic, доменные ошибки в модели,
тело ответа в формате Problem Details, правильные коды.

**Проверка:** каждый сценарий отказа отвечает своим кодом, а не пятисоткой.

## Шаг 4. Правило внутри модели

**Материал:** [/domain-driven-design/01-what-is-ddd/](https://vikulin-va.ru/domain-driven-design/01-what-is-ddd/) · [/python/oop/](https://vikulin-va.ru/python/oop/) · [/domain-driven-design/python/03-tactical-patterns/](https://vikulin-va.ru/domain-driven-design/python/03-tactical-patterns/)

**Даётся:** тесты домена, которым не нужна база, и проверка, что состояние меняется только методами.

**Ученик:** переносит правила в класс - скидка не больше половины, цена округляется
до копеек; наружу торчат методы и свойства только на чтение.

**Проверка:** доменные тесты зелёные и работают за миллисекунды; правило нельзя
обойти из сервиса.

## Шаг 5. База: миграции, транзакции, одновременный резерв

**Материал:** [/postgres/acid-and-isolation/](https://vikulin-va.ru/postgres/acid-and-isolation/) · [/postgres/locks/](https://vikulin-va.ru/postgres/locks/) · [/sqlalchemy/transactions-and-locking/](https://vikulin-va.ru/sqlalchemy/transactions-and-locking/) · [/concurrency/race-conditions/](https://vikulin-va.ru/concurrency/race-conditions/)

**Даётся:** тест на сто одновременных покупателей и тест, который сверяет схему
после миграций с полями модели.

**Ученик:** отделяет резерв от остатка - новая колонка `reserved` миграцией Alembic,
`available = stock - reserved`; резерв удерживает товар, а не списывает его.
Дальше разбирается, почему при обычном чтении продаётся больше, чем есть, и берёт
строку под блокировку в транзакции.

**Проверка:** сто параллельных резервов на десять единиц продают ровно десять,
остаток на складе при этом не меняется.

## Шаг 6. Поиск: LIKE, индекс, кэш

**Материал:** [/postgres/indexes-types/](https://vikulin-va.ru/postgres/indexes-types/) · [/redis/caching-patterns/](https://vikulin-va.ru/redis/caching-patterns/) · [/redis/python/redis-py/](https://vikulin-va.ru/redis/python/redis-py/) · [/algorithms/](https://vikulin-va.ru/algorithms/)

**Даётся:** генератор на сто тысяч товаров, скрипт замера и тест, который считает
обращения к базе.

**Ученик:** снимает время ответа на ста тысячах товаров, видит `Seq Scan` в плане,
заводит триграммный индекс миграцией, потом кладёт карточку товара в кэш и
сбрасывает запись при любом изменении.

**Проверка:** время ответа до и после - числом; повторный запрос отвечает из кэша,
правка товара кэш сбрасывает.

# Часть вторая: взрослая система

## Шаг 7. Тот же каталог, но по-взрослому

**Материал:** [/use-case-pattern/](https://vikulin-va.ru/use-case-pattern/) · [/patterns/hexagonal/python/core-layer/](https://vikulin-va.ru/patterns/hexagonal/python/core-layer/) · [/patterns/hexagonal/python/architecture-tests/](https://vikulin-va.ru/patterns/hexagonal/python/architecture-tests/) · [/use-case-pattern/case/](https://vikulin-va.ru/use-case-pattern/case/)

**Даётся:** `services/catalog` - ядро без единого импорта FastAPI и SQLAlchemy, порты протоколами,
спецификация, роли и владение, журнал действий администратора; архитектурный тест на
направление импортов и интеграционные тесты смены цены на настоящей PostgreSQL.

**Ученик:** сравнивает две версии одного сервиса и письменно отвечает, что дала
сложность и чего стоила; потом переносит смену цены из третьего шага сюда - команда,
обработчик сценария, метод порта, запрос в адаптере, роутер.

**Проверка:** шесть проверок смены цены зелёные - цена меняется и доезжает до базы,
ноль не проходит, чужой товар отдаёт 404, админское изменение оставляет запись в
журнале, без токена 401; архитектурный тест по-прежнему зелёный.

## Шаг 8. Заказ: сосед отвечает медленно, срывается и лежит

**Материал:** [/patterns/python/resilience/](https://vikulin-va.ru/patterns/python/resilience/) · [/architecture-choice/monolith-vs-microservices/](https://vikulin-va.ru/architecture-choice/monolith-vs-microservices/) · [/use-case-pattern/case/order-service/](https://vikulin-va.ru/use-case-pattern/case/order-service/)

**Даётся:** `services/order` - агрегат заказа, сценарий создания черновика, который ходит в
`catalog` за ценами, хранение на SQLAlchemy и тесты, где каталог подменён локальным HTTP-сервером:
он умеет держать ответ, рвать соединение и отвечать 404.

**Ученик:** в клиенте каталога на `httpx` ставит таймауты на соединение и на запрос, повтор с паузой
только для сетевых ошибок и 5xx, размыкатель; исчерпанные попытки и открытый размыкатель
превращает в доменное `SERVICE_DEGRADED`, а 404 каталога оставляет `PRODUCT_NOT_FOUND` без повтора.

**Проверка:** четыре проверки клиента зелёные - зависший первый ответ переживается повтором,
лежащий каталог даёт 503 и ноль заказов в базе, медленный каталог отбивается таймаутом,
после серии отказов размыкатель перестаёт ходить к каталогу.

## Шаг 9. Идемпотентность

**Материал:** [/rest-api/python/headers/](https://vikulin-va.ru/rest-api/python/headers/) · [/graceful-shutdown/python/idempotency-in-flight/](https://vikulin-va.ru/graceful-shutdown/python/idempotency-in-flight/)

**Даётся:** заголовок `Idempotency-Key` и хеш тела уже доезжают до сценария, таблица
`idempotency_keys` в миграциях, порт ключей, тесты, которые шлют один и тот же запрос дважды
и восемь раз разом.

**Ученик:** проверка ключа до работы, занятие ключа вставкой с `ON CONFLICT DO NOTHING` в одной
транзакции с заказом, ответ проигравшему гонку прежним заказом, конфликт хеша тела кодом
`IDEMPOTENCY_KEY_CONFLICT`.

**Проверка:** повтор не создаёт второй заказ и возвращает тот же ответ, другой текст под тем
же ключом даёт 409, восемь одновременных запросов дают один заказ.

## Шаг 10. События, outbox и контракт

**Материал:** [/kafka/python/fundamentals/](https://vikulin-va.ru/kafka/python/fundamentals/) · [/patterns/python/distributed-patterns/](https://vikulin-va.ru/patterns/python/distributed-patterns/) · [/graceful-shutdown/python/scheduled-async-outbox/](https://vikulin-va.ru/graceful-shutdown/python/scheduled-async-outbox/) · [/kafka/python/production-essentials/](https://vikulin-va.ru/kafka/python/production-essentials/)

**Даётся:** таблица `outbox`, агрегат, который регистрирует `OrderCreated`, издатель на aiokafka, Kafka в
стенде, контракт событий в `contracts/` (AsyncAPI плюс пакет типов) и сервис `notification`
с консьюмером и журналом `processed_events`.

**Ученик:** пишет событие в outbox в одной транзакции с заказом, собирает payload по внешнему
контракту, а не из внутреннего типа, и делает relay: пачка под `FOR UPDATE SKIP LOCKED`,
публикация, пометка отправленного в той же транзакции.

**Проверка:** строка outbox рождается вместе с заказом и не рождается при откате; поля payload
ровно те, что в контракте; relay публикует и помечает, при лежащем брокере строка остаётся;
повторная доставка в `notification` не создаёт второе уведомление.

## Шаг 11. Сага и статусная модель заказа

**Материал:** [/patterns/python/distributed-patterns/](https://vikulin-va.ru/patterns/python/distributed-patterns/) · [/state-machines/python/implementation/](https://vikulin-va.ru/state-machines/python/implementation/) · [/patterns/python/resilience/](https://vikulin-va.ru/patterns/python/resilience/)

**Даётся:** заказ со статусной моделью в агрегате, сага отмены оплаченного заказа с возвратом
через `payment`, потребитель `PaymentCompleted` с защитой от повтора, фоновая просрочка оплаты;
каркас `services/payment` на `asyncpg` без ORM с тестами.

**Ученик:** в сервисе платежей описывает автомат статусов разрешёнными переходами, делает одну
авторизацию на заказ и безопасный повторный возврат.

**Проверка:** переходы ровно те, что описаны, конечные статусы никуда не ведут, повторная
авторизация возвращает прежний платёж, списать возвращённый платёж нельзя, повторный возврат
отвечает тем же, а в заказе отказ платежей откатывает отмену.

## Шаг 12. Токены, роли и файлы

**Материал:** [/patterns/auth-patterns/python/jwt-validation/](https://vikulin-va.ru/patterns/auth-patterns/python/jwt-validation/) · [/keycloak/python/roles-and-access/](https://vikulin-va.ru/keycloak/python/roles-and-access/) · [/object-storage/python/boto3-s3/](https://vikulin-va.ru/object-storage/python/boto3-s3/) · [/patterns/hexagonal/python/adapters-out/](https://vikulin-va.ru/patterns/hexagonal/python/adapters-out/)

**Даётся:** каталог с проверкой токена по ключам Keycloak без похода в соседний сервис, роли
`seller` и `admin` в зависимостях, MinIO в стенде с готовой корзиной `marketplace-images`, порт
`ImageStorage`, адаптер на boto3 и ручка `POST /api/v1/products/{id}/image-upload-url`.

**Ученик:** подписывает временную ссылку на загрузку; в сценарии проверяет владение товаром:
чужой товар для не-владельца выглядит как несуществующий, 404 `OWN_PRODUCT_REQUIRED`, а не 403.

**Проверка:** владелец получает ссылку с подписью и сроком; чужой товар даёт 404 с кодом владения;
неизвестный товар даёт 404; без токена ссылки нет; не картинка отклоняется на входе.

## Шаг 13. Граница системы: экран и лимит частоты

**Материал:** [/patterns/python/microservices-structural/](https://vikulin-va.ru/patterns/python/microservices-structural/) · [/api-styles/](https://vikulin-va.ru/api-styles/) · [/rest-api/python/rate-limiting-files-deprecation/](https://vikulin-va.ru/rest-api/python/rate-limiting-files-deprecation/) · [/redis/python/redis-py/](https://vikulin-va.ru/redis/python/redis-py/)

**Даётся:** сервис `services/bff`: ручка `GET /api/v1/screens/order/{id}`, клиенты соседей с
таймаутом и ошибкой `DownstreamError`, middleware лимита с 429 и `Retry-After`, Redis в стенде.

**Ученик:** собирает экран заказа: заказ читается первым, карточки товаров и статус платежа добираются
параллельно через `asyncio.gather`, отсутствие платежа это `NONE`; пишет счётчик запросов клиента в
Redis на минутное окно: `INCR` плюс `EXPIRE` на первом попадании.

**Проверка:** экран собирается одним запросом клиента из трёх сервисов; нет платежа, экран всё равно
собран; лежащий сосед даёт 502 `DOWNSTREAM_UNAVAILABLE`; четвёртый запрос клиента за минуту получает 429.

## Шаг 14. Веб-клиент и продуктовые числа

**Материал:** [/frontend/](https://vikulin-va.ru/frontend/) · [/product-engineer/ship-and-measure/](https://vikulin-va.ru/product-engineer/ship-and-measure/) · [/fastapi/testing/](https://vikulin-va.ru/fastapi/testing/)

**Даётся:** каталог `web/` на React, TypeScript и Vite: витрина, корзина, оформление с `Idempotency-Key`
и экран заказа через BFF; Vite в разработке играет роль шлюза к каталогу, заказам и BFF; публичная
витрина опубликованных товаров в каталоге (`GET /api/v1/products`); воронка с `FunnelSink`, отделённая
от отправки; тесты на `vitest` и `@testing-library/react` с подменённой сетью.

**Ученик:** отмечает шаги воронки в компоненте: показ карточек, корзина, начало оформления и оплата по
**реальному статусу платежа**, а не по нажатию кнопки; считает конверсию по шагам без деления на ноль.

**Проверка:** доли дошедших до каждого шага считаются как в примере 10 → 4 → 2 → 1; шаг, до которого
никто не дошёл, даёт ноль; полный путь покупки виден в воронке целиком; каталог, корзина и оформление
с ключом идемпотентности и токеном покупателя работают как раньше.

## Шаг 15. Доставка и наблюдаемость

**Материал:** [/docker/python/dockerizing/](https://vikulin-va.ru/docker/python/dockerizing/) · [/docker/python/runtime/](https://vikulin-va.ru/docker/python/runtime/) · [/kubernetes/](https://vikulin-va.ru/kubernetes/) · [/observability/python/health-checks/](https://vikulin-va.ru/observability/python/health-checks/) · [/observability/python/metrics/](https://vikulin-va.ru/observability/python/metrics/) · [/cicd/](https://vikulin-va.ru/cicd/)

**Даётся:** черновой `Dockerfile` стартового каталога, манифест `deploy/k8s/catalog-starter.yaml`
без проб и лимитов, эталонный `deploy/k8s/bff.yaml`, пайплайн `.github/workflows/ci.yml`,
проверка выката `tools/check-deploy.py`, модуль `observability` с гистограммой времени ответа на
`prometheus_client` и трассировкой на OpenTelemetry.

**Ученик:** собирает образ в два этапа без инструментов сборки и без root; в манифесте заводит пробы,
запросы и лимиты, `preStop` и версию образа вместо `latest`; монтирует пробы и `/metrics` с меткой
сервиса и включает сэмплирование трасс по доле из настроек.

**Проверка:** `tools/check-deploy.py` без замечаний, четыре проверки наблюдаемости зелёные.
