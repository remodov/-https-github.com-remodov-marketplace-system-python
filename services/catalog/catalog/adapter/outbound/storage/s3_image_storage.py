from dataclasses import dataclass
from datetime import timedelta

import boto3
from botocore.config import Config

from ....core.product.port.out import Clock, PresignedUpload


@dataclass(frozen=True)
class StorageSettings:
    endpoint: str
    region: str
    access_key: str
    secret_key: str
    bucket: str
    upload_ttl_seconds: int


class S3ImageStorage:
    def __init__(self, settings: StorageSettings, clock: Clock) -> None:
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint,
            region_name=settings.region,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self.bucket = settings.bucket
        self.upload_ttl = timedelta(seconds=settings.upload_ttl_seconds)
        self.clock = clock

    def presign_upload(self, key: str, content_type: str) -> PresignedUpload:
        # TODO шаг 12: подписанная ссылка на PUT объекта.
        # Тип содержимого должен войти в подпись, срок жизни берётся из настроек,
        # expires_at считается от часов сервиса. Клиент уже знает регион и в сеть не ходит.
        raise NotImplementedError("шаг 12: ссылка на загрузку не реализована")
