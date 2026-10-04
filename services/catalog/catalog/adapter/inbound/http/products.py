import uuid

from fastapi import APIRouter, Depends, Query, Response

from ....core.product.aggregate.product import Status
from ....core.product.port.out import ListFilter, SortField
from ....core.product.query.queries import GetProduct, ListMyProducts, QueryHandler
from ....core.product.usecase.change_product_price import ChangeProductPrice, ChangeProductPriceHandler
from ....core.product.usecase.change_status import ChangeStatusHandler, HideProduct, PublishProduct
from ....core.product.usecase.create_product import CreateProduct, CreateProductHandler
from ....core.product.usecase.request_image_upload import RequestImageUpload, RequestImageUploadHandler
from ....core.security.principal import Principal, Role
from .auth import Authenticator, optional_principal, require_roles
from .schemas import (
    ChangePriceRequest,
    CreateProductRequest,
    ImageUploadRequest,
    ImageUploadUrlResponse,
    ProductPageResponse,
    ProductResponse,
    page_of,
    response_of,
    upload_url_of,
)


def sort_field(raw: str) -> SortField:
    try:
        return SortField(raw)
    except ValueError:
        return SortField.CREATED_AT_DESC


def product_router(
    auth: Authenticator,
    create: CreateProductHandler,
    price: ChangeProductPriceHandler,
    transitions: ChangeStatusHandler,
    queries: QueryHandler,
    uploads: RequestImageUploadHandler,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/products", tags=["products"])
    principal_of = optional_principal(auth)
    seller_or_admin = require_roles(principal_of, Role.SELLER, Role.ADMIN)

    @router.post("", status_code=201)
    async def create_product(
        body: CreateProductRequest,
        response: Response,
        principal: Principal = Depends(seller_or_admin),
    ) -> ProductResponse:
        product = await create.handle(
            CreateProduct(
                seller=principal,
                title=body.title,
                description=body.description,
                price=body.price,
                currency=body.currency,
            )
        )
        response.headers["Location"] = f"/api/v1/products/{product.id}"
        return response_of(product)

    @router.get("/my")
    async def list_my_products(
        principal: Principal = Depends(seller_or_admin),
        status: Status | None = Query(None),
        page: int = Query(1),
        size: int = Query(20),
        sort: str = Query(SortField.CREATED_AT_DESC.value),
    ) -> ProductPageResponse:
        list_filter = ListFilter(status=status, page=page, size=size, sort=sort_field(sort))
        found = await queries.list_my_products(ListMyProducts(seller=principal.sub, list_filter=list_filter))
        return page_of(found)

    @router.get("/{product_id}")
    async def get_product(
        product_id: uuid.UUID,
        principal: Principal | None = Depends(principal_of),
    ) -> ProductResponse:
        product = await queries.get_product(GetProduct(product_id=product_id, requester=principal))
        return response_of(product)

    @router.post("/{product_id}/publish")
    async def publish_product(
        product_id: uuid.UUID,
        principal: Principal = Depends(seller_or_admin),
    ) -> ProductResponse:
        product = await transitions.publish(PublishProduct(product_id=product_id, requester=principal))
        return response_of(product)

    @router.post("/{product_id}/hide")
    async def hide_product(
        product_id: uuid.UUID,
        principal: Principal = Depends(seller_or_admin),
    ) -> ProductResponse:
        product = await transitions.hide(HideProduct(product_id=product_id, requester=principal))
        return response_of(product)

    @router.patch("/{product_id}/price")
    async def change_product_price(
        product_id: uuid.UUID,
        body: ChangePriceRequest,
        principal: Principal = Depends(seller_or_admin),
    ) -> ProductResponse:
        product = await price.handle(
            ChangeProductPrice(product_id=product_id, requester=principal, new_price=body.price)
        )
        return response_of(product)

    @router.post("/{product_id}/image-upload-url")
    async def request_image_upload(
        product_id: uuid.UUID,
        body: ImageUploadRequest,
        principal: Principal = Depends(seller_or_admin),
    ) -> ImageUploadUrlResponse:
        upload = await uploads.handle(
            RequestImageUpload(product_id=product_id, requester=principal, content_type=body.content_type)
        )
        return upload_url_of(upload)

    return router
