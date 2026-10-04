import ast
from pathlib import Path

import catalog
from catalog.adapter.outbound.persistence.audit_repository import SqlAlchemyAuditLogger
from catalog.adapter.outbound.persistence.product_repository import SqlAlchemyProductRepository
from catalog.adapter.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from catalog.adapter.outbound.system.system import SystemClock, UuidGenerator
from catalog.core.product.port.out import AuditLogger, Clock, IdGenerator, ProductRepository, UnitOfWork

PACKAGE = "catalog"
PACKAGE_ROOT = Path(catalog.__file__).resolve().parent

FORBIDDEN_IN_CORE = (
    "fastapi",
    "starlette",
    "sqlalchemy",
    "asyncpg",
    "alembic",
    "pydantic",
    "pydantic_settings",
    "jwt",
    "uvicorn",
    "httpx",
)


def module_name(path: Path) -> str:
    parts = list(path.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(path: Path) -> set[str]:
    module = module_name(path)
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                found.add(node.module or "")
            else:
                base = package.rsplit(".", node.level - 1)[0]
                found.add(f"{base}.{node.module}" if node.module else base)
    return found


def modules_under(subpackage: str) -> dict[str, set[str]]:
    files = sorted((PACKAGE_ROOT / subpackage).rglob("*.py"))
    assert files, f"в {subpackage} не найдено ни одного модуля"
    return {module_name(path): imports_of(path) for path in files}


def test_core_depends_only_on_core_and_stdlib():
    violations = []
    for module, imports in modules_under("core").items():
        for imported in imports:
            if imported.split(".")[0] in FORBIDDEN_IN_CORE:
                violations.append(f"модуль ядра {module} импортирует технологию {imported}")
            if imported.startswith((f"{PACKAGE}.adapter", f"{PACKAGE}.bootstrap")):
                violations.append(f"модуль ядра {module} импортирует {imported}")
    assert not violations, "\n".join(violations)


def test_inbound_adapters_do_not_import_outbound():
    violations = [
        f"входной адаптер {module} импортирует выходной {imported}"
        for module, imports in modules_under("adapter/inbound").items()
        for imported in imports
        if imported.startswith(f"{PACKAGE}.adapter.outbound")
    ]
    assert not violations, "\n".join(violations)


def test_outbound_adapters_do_not_import_each_other():
    prefix = f"{PACKAGE}.adapter.outbound."
    violations = []
    for module, imports in modules_under("adapter/outbound").items():
        if not module.startswith(prefix):
            continue
        own = module.removeprefix(prefix).split(".")[0]
        for imported in imports:
            if imported.startswith(prefix) and not imported.startswith(prefix + own):
                violations.append(f"выходной адаптер {module} импортирует соседний {imported}")
    assert not violations, "\n".join(violations)


def test_adapters_satisfy_ports():
    sessions = object()
    assert isinstance(SqlAlchemyProductRepository(sessions), ProductRepository)
    assert isinstance(SqlAlchemyAuditLogger(sessions), AuditLogger)
    assert isinstance(SqlAlchemyUnitOfWork(sessions), UnitOfWork)
    assert isinstance(SystemClock(), Clock)
    assert isinstance(UuidGenerator(), IdGenerator)
