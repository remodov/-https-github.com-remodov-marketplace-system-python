import uuid
from dataclasses import dataclass

from ...security.principal import Principal
from ..port.out import IdGenerator, ImageStorage, PresignedUpload, ProductRepository
from .ownership import require_ownership


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
        require_ownership(product, cmd.requester)
        key = f"products/{product.id}/{self.ids.new_id()}"
        return self.images.presign_upload(key, cmd.content_type)
