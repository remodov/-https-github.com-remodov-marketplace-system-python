from ...errors import not_found
from ...security.principal import Principal
from ..aggregate.product import Product


def require_ownership(product: Product, requester: Principal) -> None:
    if requester.is_admin or product.owned_by(requester.sub):
        return
    raise not_found("OWN_PRODUCT_REQUIRED", "Продукт не найден")
