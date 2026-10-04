import uuid
from decimal import Decimal

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from .card import Card, card_of
from .service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


class CreateProduct(BaseModel):
    title: str = Field(min_length=1)
    price: Decimal = Field(gt=0)
    stock: int = Field(ge=0)


class Reserve(BaseModel):
    quantity: int = Field(ge=1)


def service_of(request: Request) -> ProductService:
    return request.app.state.products


@router.get("")
async def search(
    request: Request,
    query: str = "",
) -> list[Card]:
    # TODO шаг 2: необязательный параметр maxPrice (Query с alias и gt=0) и выбор сценария
    found = await service_of(request).search(query)
    return [card_of(p) for p in found]


@router.get("/{id}")
async def by_id(request: Request, id: uuid.UUID) -> Card:
    return card_of(await service_of(request).by_id(id))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(request: Request, body: CreateProduct) -> Card:
    created = await service_of(request).create(body.title, body.price, body.stock)
    return card_of(created)


@router.post("/{id}/reserve")
async def reserve(request: Request, id: uuid.UUID, body: Reserve) -> Card:
    return card_of(await service_of(request).reserve(id, body.quantity))
