import uuid


class NotFoundError(Exception):
    def __init__(self, product_id: uuid.UUID) -> None:
        super().__init__(f"Товар {product_id} не найден")
        self.product_id = product_id


class InvalidError(Exception):
    pass


class ConflictError(Exception):
    def __init__(self) -> None:
        super().__init__("Товар изменили параллельно, повторите запрос")


class OutOfStockError(Exception):
    def __init__(self, product_id: uuid.UUID, requested: int, available: int) -> None:
        super().__init__(f"Товара {product_id} не хватает: просят {requested}, на складе {available}")
        self.product_id = product_id
        self.requested = requested
        self.available = available


def invalid(message: str) -> InvalidError:
    return InvalidError(f"Недопустимое значение: {message}")
