import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ....core.errors import AppError, Kind

log = logging.getLogger("order.http")

PROBLEM = "application/problem+json"

STATUS_BY_KIND = {
    Kind.INVALID: 400,
    Kind.NOT_FOUND: 404,
    Kind.FORBIDDEN: 403,
    Kind.CONFLICT: 409,
    Kind.UNAUTHORIZED: 401,
    Kind.UNAVAILABLE: 503,
}

MESSAGES = {
    "missing": "обязательное поле",
    "too_short": "нужна хотя бы одна позиция",
    "greater_than_equal": "слишком маленькое значение",
    "less_than_equal": "слишком большое значение",
    "string_too_short": "не может быть пустым",
    "string_too_long": "слишком длинное",
    "int_parsing": "должно быть целым числом",
    "int_type": "должно быть целым числом",
    "string_type": "должно быть строкой",
    "uuid_parsing": "должен быть UUID",
    "uuid_type": "должен быть UUID",
    "model_type": "должен быть объектом",
    "dict_type": "должен быть объектом",
    "list_type": "должен быть списком",
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
        "type": f"urn:problem:order:{code}",
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


def field_path(location: tuple[object, ...]) -> str:
    path = ""
    for part in location:
        if part in ("body", "header") and not path:
            continue
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path = f"{path}.{part}" if path else str(part)
    return path or "body"


def is_unreadable_body(location: tuple[object, ...], kind: str) -> bool:
    return kind == "json_invalid" or location == ("body",)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def on_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.kind is Kind.UNAVAILABLE:
            log.warning("сосед недоступен на %s: %s", request.url.path, exc.__cause__ or exc)
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
            errors[field_path(location)] = MESSAGES.get(kind, "недопустимое значение")
        return problem(400, "VALIDATION_ERROR", "Ошибка валидации входных данных", request.url.path, errors)

    @app.exception_handler(Exception)
    async def on_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("необработанная ошибка на %s", request.url.path)
        return problem(500, "INTERNAL_SERVER_ERROR", "Внутренняя ошибка сервиса", request.url.path)
