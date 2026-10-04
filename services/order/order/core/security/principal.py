import uuid
from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    SELLER = "seller"
    ADMIN = "admin"
    CUSTOMER = "customer"


@dataclass(frozen=True)
class Principal:
    sub: uuid.UUID
    roles: frozenset[str]

    def has_role(self, role: Role) -> bool:
        return role in self.roles

    @property
    def is_admin(self) -> bool:
        return self.has_role(Role.ADMIN)
