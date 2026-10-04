# Шаг 7. Тот же каталог, но по-взрослому

Рядом с учебным `catalog-starter` лежит `services/catalog` - тот же сервис, собранный так,
как его собирают в большой системе: ядро без импортов FastAPI и SQLAlchemy, порты протоколами,
спецификация в `docs/spec/`, роли и владение, журнал действий администратора.

## Часть первая: сравнить

Откройте оба сервиса и ответьте письменно (хватит десяти строк в `docs/COMPARISON.md`):

1. Что в `services/catalog` стало возможным, чего в `catalog-starter` не было?
   Подсказка: тест ядра без базы, второй вход (Kafka), смена хранилища, проверка границ.
2. Чего это стоило: сколько файлов нужно открыть, чтобы добавить поле в карточку, здесь и там.
3. При каком размере команды и сервиса вы бы остались на простой раскладке.

## Часть вторая: перенести смену цены

Смена цены из шага 3 в этом сервисе вынута. Шесть тестов `test_change_price_*` в
`tests/test_change_price.py` красные. Верните команду по слоям:

- `catalog/core/product/usecase/change_product_price.py` - команда `ChangeProductPrice`
  и обработчик `ChangeProductPriceHandler`; смотрите на `change_status.py` как на образец:
  единица работы, строка под `FOR UPDATE`, владение через `require_ownership`, журнал для администратора.
- `catalog/core/product/aggregate/product.py` - метод `change_price`: правило BR-P01, цена больше нуля,
  округление до копеек, `updated_at`.
- `catalog/adapter/inbound/http/products.py` - маршрут `PATCH /api/v1/products/{product_id}/price`
  и функция-обработчик: тело `ChangePriceRequest` (ноль отсекает схема, `VALIDATION_ERROR` до вызова ядра),
  вызов обработчика сценария, ответ `ProductResponse`.
- `catalog/bootstrap/wire.py` - обработчик сценария собирается здесь и передаётся в `product_router`;
  сверьте, что он получает те же порты, что `ChangeStatusHandler`.

Места отмечены `TODO шаг 7`.

## Проверка

```bash
python -m pytest -q
```

Зелёными должны стать шесть `test_change_price_*` и остаться зелёными архитектурные тесты:
если смена цены потянула в ядро `sqlalchemy` или `fastapi`, `test_core_depends_only_on_core_and_stdlib`
упадёт первым.

## Куда смотреть

- [Use Case Pattern](https://vikulin-va.ru/use-case-pattern/) - почему команда и обработчик, а не сервис с методами.
- [Core слой на Python](https://vikulin-va.ru/patterns/hexagonal/python/core-layer/) и [порты](https://vikulin-va.ru/patterns/hexagonal/python/ports/).
- [Архитектурные тесты на Python](https://vikulin-va.ru/patterns/hexagonal/python/architecture-tests/) - как тест читает импорты через `ast`.
- [ABAC и владение ресурсом в Python](https://vikulin-va.ru/patterns/auth-patterns/python/abac-resource-ownership/) - почему чужой товар это 404.
- [Журнал действий администратора в Python](https://vikulin-va.ru/patterns/auth-patterns/python/audit-admin/).
- [Маркетплейс-кейс целиком](https://vikulin-va.ru/use-case-pattern/case/) - где Catalog стоит среди соседей.
