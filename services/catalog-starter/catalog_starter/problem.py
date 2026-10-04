from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .product.errors import ConflictError, InvalidError, NotFoundError, OutOfStockError

PROBLEM = "application/problem+json"

MESSAGES = {
    "missing": "обязательно",
    "greater_than": "должно быть больше нуля",
    "greater_than_equal": "не может быть отрицательным",
    "string_too_short": "не может быть пустым",
    "int_parsing": "должно быть целым числом",
    "int_type": "должно быть целым числом",
    "decimal_parsing": "должно быть числом",
    "decimal_type": "должно быть числом",
    "float_parsing": "должно быть числом",
    "string_type": "должно быть строкой",
    "uuid_parsing": "должен быть UUID",
}


def problem(status: int, detail: str, instance: str, errors: dict[str, str] | None = None) -> JSONResponse:
    body = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": instance,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM)


def field_errors(status: int, detail: str, instance: str, errors: dict[str, str]) -> JSONResponse:
    return problem(status, detail, instance, errors)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors: dict[str, str] = {}
        for item in exc.errors():
            location = item.get("loc", ())
            if location and location[0] == "path" and "id" in location:
                return problem(400, "Идентификатор товара должен быть UUID", request.url.path)
            field = str(location[-1]) if location else "body"
            if field == "body":
                return problem(400, "Тело запроса не разобрать", request.url.path)
            errors[field] = MESSAGES.get(item.get("type", ""), "недопустимое значение")
        return field_errors(400, "Запрос не прошёл проверку", request.url.path, errors)

    @app.exception_handler(NotFoundError)
    async def on_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return problem(404, str(exc), request.url.path)

    @app.exception_handler(OutOfStockError)
    async def on_out_of_stock(request: Request, exc: OutOfStockError) -> JSONResponse:
        return problem(409, str(exc), request.url.path)

    @app.exception_handler(ConflictError)
    async def on_conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return problem(409, str(exc), request.url.path)

    @app.exception_handler(InvalidError)
    async def on_invalid(request: Request, exc: InvalidError) -> JSONResponse:
        return problem(400, str(exc), request.url.path)
