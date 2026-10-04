import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ....core.errors import AppError, forbidden, unauthorized
from ....core.security.principal import Principal, Role


class Authenticator(Protocol):
    def authenticate(self, token: str) -> Principal: ...


class LocalTokens:
    def authenticate(self, token: str) -> Principal:
        role, separator, raw_id = token.partition(".")
        if not separator:
            raise token_invalid("локальный токен имеет вид role.uuid")
        try:
            sub = uuid.UUID(raw_id)
        except ValueError as error:
            raise token_invalid(f"идентификатор в токене: {error}") from error
        return Principal(sub=sub, roles=frozenset({role}))


class JwtAuthenticator:
    def __init__(self, jwks_url: str, issuer: str, audience: str) -> None:
        self.jwks = jwt.PyJWKClient(jwks_url)
        self.issuer = issuer
        self.audience = audience or None

    def authenticate(self, token: str) -> Principal:
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256", "ES256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "sub"], "verify_aud": self.audience is not None},
            )
        except jwt.PyJWTError as error:
            raise token_invalid(str(error)) from error
        try:
            sub = uuid.UUID(str(claims["sub"]))
        except ValueError as error:
            raise token_invalid(f"sub в токене: {error}") from error
        return Principal(sub=sub, roles=frozenset(realm_roles(claims)))


def realm_roles(claims: dict[str, Any]) -> list[str]:
    access = claims.get("realm_access")
    if not isinstance(access, dict):
        return []
    roles = access.get("roles")
    if not isinstance(roles, list):
        return []
    return [role for role in roles if isinstance(role, str)]


def token_invalid(reason: str) -> AppError:
    return unauthorized("TOKEN_INVALID", f"Токен не принят: {reason}")


bearer = HTTPBearer(auto_error=False)

PrincipalDependency = Callable[..., Awaitable[Principal | None]]


def optional_principal(auth: Authenticator) -> PrincipalDependency:
    async def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> Principal | None:
        if credentials is None:
            return None
        return auth.authenticate(credentials.credentials)

    return dependency


def require_roles(principal_of: PrincipalDependency, *roles: Role) -> Callable[..., Awaitable[Principal]]:
    async def dependency(principal: Principal | None = Depends(principal_of)) -> Principal:
        if principal is None:
            raise unauthorized("TOKEN_MISSING", "Требуется аутентификация")
        if not any(principal.has_role(role) for role in roles):
            raise forbidden("ACCESS_DENIED", "Доступ запрещён")
        return principal

    return dependency
