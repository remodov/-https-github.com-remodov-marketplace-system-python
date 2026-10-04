import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ....core.errors import AppError, Kind

log = logging.getLogger("catalog.http")

PROBLEM = "application/problem+json"

STATUS_BY_KIND = {
    Kind.INVALID: 400,
    Kind.NOT_FOUND: 404,
    Kind.FORBIDDEN: 403,
    Kind.CONFLICT: 409,
    Kind.UNAUTHORIZED: 401,
}

MESSAGES = {
    "missing": "обязательное поле",
    "greater_than": "должно быть больше нуля",
    "greater_than_equal": "не может быть отрицательным",
    "string_too_short": "не может быть пустым",
    "string_too_long": "слишком длинное",
    "int_parsing": "должно быть целым числом",
    "int_type": "должно быть целым числом",
    "decimal_parsing": "должно быть числом",
    "decimal_type": "должно быть числом",
    "string_type": "должно быть строкой",
    "uuid_parsing": "должен быть UUID",
    "enum": "недопустимое значение",
}


def problem(
    status: int,
    code: str,
    detail: str,
    instance: str,
    errors: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"urn:problem:catalog:{code}",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM, headers=headers)


def challenge(error: AppError) -> dict[str, str] | None:
    if error.kind is not Kind.UNAUTHORIZED:
        return None
    if error.code == "TOKEN_INVALID":
        return {"WWW-Authenticate": 'Bearer error="invalid_token"'}
    return {"WWW-Authenticate": "Bearer"}


def camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


def is_unreadable_body(location: tuple[object, ...], kind: str) -> bool:
    return kind == "json_invalid" or location == ("body",)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def on_app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem(
            STATUS_BY_KIND[exc.kind], exc.code, exc.message, request.url.path, headers=challenge(exc)
        )

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors: dict[str, str] = {}
        for item in exc.errors():
            location = tuple(item.get("loc", ()))
            kind = str(item.get("type", ""))
            if is_unreadable_body(location, kind):
                return problem(
                    400, "MALFORMED_REQUEST", "Невозможно разобрать тело запроса", request.url.path
                )
            field = camel(str(location[-1])) if location else "body"
            errors[field] = MESSAGES.get(kind, "недопустимое значение")
        return problem(400, "VALIDATION_ERROR", "Ошибка валидации входных данных", request.url.path, errors)

    @app.exception_handler(Exception)
    async def on_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("необработанная ошибка на %s", request.url.path)
        return problem(500, "INTERNAL_SERVER_ERROR", "Внутренняя ошибка сервиса", request.url.path)
