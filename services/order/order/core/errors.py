from enum import Enum


class Kind(Enum):
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    CONFLICT = "conflict"
    UNAUTHORIZED = "unauthorized"
    UNAVAILABLE = "unavailable"


class AppError(Exception):
    def __init__(self, kind: Kind, code: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.code = code
        self.message = message


def invalid(code: str, message: str) -> AppError:
    return AppError(Kind.INVALID, code, message)


def not_found(code: str, message: str) -> AppError:
    return AppError(Kind.NOT_FOUND, code, message)


def forbidden(code: str, message: str) -> AppError:
    return AppError(Kind.FORBIDDEN, code, message)


def conflict(code: str, message: str) -> AppError:
    return AppError(Kind.CONFLICT, code, message)


def unauthorized(code: str, message: str) -> AppError:
    return AppError(Kind.UNAUTHORIZED, code, message)


def unavailable(code: str, message: str) -> AppError:
    return AppError(Kind.UNAVAILABLE, code, message)
