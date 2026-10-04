import uuid
from decimal import Decimal

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, Field

from .card import Card, card_of
from .service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


class CreateProduct(BaseModel):
    title: str = Field(min_length=1)
    price: Decimal = Field(gt=0)
    stock: int = Field(ge=0)


class ChangePrice(BaseModel):
    price: Decimal = Field(gt=0)


# TODO шаг 4: модель ApplyDiscount с обязательным целым percent


class ChangeStock(BaseModel):
    delta: int


class Reserve(BaseModel):
    quantity: int = Field(ge=1)


def service_of(request: Request) -> ProductService:
    return request.app.state.products


@router.get("")
async def search(
    request: Request,
    query: str = "",
    max_price: Decimal | None = Query(None, alias="maxPrice", gt=0),
) -> list[Card]:
    service = service_of(request)
    found = await service.search(query) if max_price is None else await service.cheaper_than(max_price)
    return [card_of(p) for p in found]


@router.get("/{id}")
async def by_id(request: Request, id: uuid.UUID) -> Card:
    return card_of(await service_of(request).by_id(id))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(request: Request, body: CreateProduct) -> Card:
    created = await service_of(request).create(body.title, body.price, body.stock)
    return card_of(created)


@router.patch("/{id}/price")
async def change_price(request: Request, id: uuid.UUID, body: ChangePrice) -> Card:
    return card_of(await service_of(request).change_price(id, body.price))


# TODO шаг 4: PATCH /{id}/discount с телом {"percent": N}


@router.patch("/{id}/stock")
async def change_stock(request: Request, id: uuid.UUID, body: ChangeStock) -> Card:
    return card_of(await service_of(request).change_stock(id, body.delta))


@router.post("/{id}/reserve")
async def reserve(request: Request, id: uuid.UUID, body: Reserve) -> Card:
    return card_of(await service_of(request).reserve(id, body.quantity))
