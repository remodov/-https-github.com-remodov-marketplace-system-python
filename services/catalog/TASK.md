# Шаг 12. Токены, роли и файлы

## Что нужно сделать

У карточки появляются фотографии. Первое желание - принять файл ручкой сервиса и
положить в хранилище самому. Так делать не надо: сервис на каждую картинку держит
корутину и буфер в памяти, воркеров у uvicorn немного, а на десяти мегабайтах и
сотне продавцов это кончается предсказуемо.

Правильный путь: сервис выдаёт **временную подписанную ссылку**, браузер кладёт
файл прямо в хранилище, мимо сервиса. Сервис решает только одно - кому эту
ссылку выдать.

```
POST /api/v1/products/{productId}/image-upload-url   {"contentType": "image/jpeg"}
-> { "key": "products/<id>/<uuid>", "url": "http://...?X-Amz-Signature=...", "expiresAt": "..." }
```

Две части:

1. **Подпись ссылки.** `S3ImageStorage.presign_upload` подписывает ссылку на
   `PUT` объекта на срок из настроек. Клиент `boto3` уже собран на хранилище
   стенда и знает регион - в сеть при подписи он не ходит. Тип содержимого входит
   в подпись: ссылка на `image/jpeg` не примет архив.
2. **Кто имеет право.** Карточку смотреть может кто угодно, а грузить в неё
   файлы - только владелец. Чужой товар для не-владельца выглядит как
   несуществующий: 404, а не 403. Ключ объекта собирает сценарий: он должен
   говорить, чей это файл.

## Где править

`# TODO шаг 12`:

- `catalog/adapter/outbound/storage/s3_image_storage.py`;
- `catalog/core/product/usecase/request_image_upload.py`.

## Как проверить себя

```bash
docker compose -f ../../infra/compose.yaml up -d postgres-catalog-starter minio minio-init
python -m pytest -q tests/test_image_upload.py
```

Красные `test_image_upload_owner_gets_presigned_url` и
`test_image_upload_foreign_product_looks_missing`: владелец получает ссылку с
подписью и сроком, чужой товар даёт 404 с кодом `OWN_PRODUCT_REQUIRED`. Остальные
три проверки уже зелёные, это даётся: `test_image_upload_unknown_product_is_not_found`
(неизвестный товар), `test_image_upload_anonymous_is_rejected` (без токена),
`test_image_upload_rejects_non_image_type` (не картинка).

Для тестов MinIO не нужен: подпись считается локально. Хранилище понадобится,
когда захочешь проверить загрузку руками: консоль MinIO на 9005, логин и пароль
`marketplace`, корзина `marketplace-images`.

## Грабли подписи

- `generate_presigned_url("put_object", Params={...}, ExpiresIn=...)`: `ContentType`
  в `Params` попадает в подпись, в ссылке это видно по
  `X-Amz-SignedHeaders=content-type;host`. Забудешь - ссылка примет что угодно;
  поставишь, а клиент пошлёт другой `Content-Type` - хранилище ответит 403
  `SignatureDoesNotMatch`.
- `Config(signature_version="s3v4", s3={"addressing_style": "path"})`: без `path`
  boto3 соберёт ссылку на поддомен `marketplace-images.localhost:9004`, которую
  локальный MinIO не поймёт. Регион тоже входит в подпись, поэтому он в настройках.
- Часы. В ссылке есть `X-Amz-Date`, и хранилище сверяет её со своими часами. А
  `expiresAt` в ответе считай от часов сервиса (`Clock`), не от `datetime.now()`:
  тест подставляет фиксированные часы и ждёт ровно `NOW + TTL`.

## На что посмотреть по дороге

- Проверка токена здесь идёт **без похода в соседний сервис**: в режиме
  `AUTH_MODE=jwt` подпись проверяется локально по ключам Keycloak через
  `PyJWKClient` из PyJWT (`JwtAuthenticator`): ключ берётся по `kid` из JWKS и
  кэшируется. Иначе каждый запрос к каталогу превращался бы в два, и падение
  соседа гасило бы всю систему.
- Роль в токене (`seller`, `admin`) отвечает на вопрос «что этому пользователю
  вообще можно», а владение товаром - «можно ли ему вот этот объект». Это разные
  проверки, и вторую нельзя заменить первой.
- Почему 404, а не 403 на чужой товар: по разнице кодов можно перебором узнать,
  какие идентификаторы существуют.
- Срок жизни ссылки: десять минут - это компромисс. Что случится, если поставить
  сутки? А если минуту?
- Проверь, что в ссылке действительно есть подпись и срок - тест смотрит именно
  на это, а не на то, что ссылка «какая-то есть».

## Материал

- Проверка JWT в Python: https://vikulin-va.ru/patterns/auth-patterns/python/jwt-validation/
- Роли Keycloak в Python: https://vikulin-va.ru/keycloak/python/roles-and-access/
- S3 из Python через boto3: https://vikulin-va.ru/object-storage/python/boto3-s3/
- Выходные адаптеры: https://vikulin-va.ru/patterns/hexagonal/python/adapters-out/
