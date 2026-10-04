from http import HTTPStatus

from fastapi.responses import JSONResponse

PROBLEM = "application/problem+json"


def problem(status: int, code: str, detail: str, instance: str) -> JSONResponse:
    body = {
        "type": f"urn:problem:bff:{code}",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM)
