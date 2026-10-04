import uuid
from dataclasses import dataclass

from ...security.principal import Principal
from ..port.out import IdGenerator, ImageStorage, PresignedUpload, ProductRepository


@dataclass(frozen=True)
class RequestImageUpload:
    product_id: uuid.UUID
    requester: Principal
    content_type: str


class RequestImageUploadHandler:
    def __init__(self, products: ProductRepository, images: ImageStorage, ids: IdGenerator) -> None:
        self.products = products
        self.images = images
        self.ids = ids

    async def handle(self, cmd: RequestImageUpload) -> PresignedUpload:
        product = await self.products.by_id(cmd.product_id)
        # TODO шаг 12: ссылку на загрузку получает только владелец товара (или администратор).
        # Карточку смотреть может кто угодно, а грузить в неё файлы - нет.
        # Чужой товар для не-владельца должен выглядеть как несуществующий.
        key = f"products/{product.id}/{self.ids.new_id()}"
        return self.images.presign_upload(key, cmd.content_type)
