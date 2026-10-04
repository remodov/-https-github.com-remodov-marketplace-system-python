import uuid
from decimal import Decimal

from pydantic import BaseModel, field_serializer

from .model import Product


class Card(BaseModel):
    id: uuid.UUID
    title: str
    price: Decimal
    stock: int

    @field_serializer("price")
    def price_as_number(self, value: Decimal) -> float:
        return float(value)


def card_of(product: Product) -> Card:
    return Card(id=product.id, title=product.title, price=product.price, stock=product.stock)
