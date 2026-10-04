import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_serializer

from ....core.product.aggregate.product import Product, Status
from ....core.product.port.out import ProductPage


class CreateProductRequest(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    description: str = ""
    price: Decimal = Field(gt=0)
    currency: Annotated[str, StringConstraints(min_length=1)]


class ChangePriceRequest(BaseModel):
    price: Decimal = Field(gt=0)


class ProductResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    price: Decimal
    currency: str
    seller_id: uuid.UUID = Field(serialization_alias="sellerId")
    status: Status
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    @field_serializer("price")
    def price_as_number(self, value: Decimal) -> float:
        return float(value)


class ProductPageResponse(BaseModel):
    items: list[ProductResponse]
    page: int
    size: int
    total: int


def response_of(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        title=product.title,
        description=product.description,
        price=product.price,
        currency=product.currency,
        seller_id=product.seller_id,
        status=product.status,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def page_of(page: ProductPage) -> ProductPageResponse:
    return ProductPageResponse(
        items=[response_of(product) for product in page.items],
        page=page.page,
        size=page.size,
        total=page.total,
    )
