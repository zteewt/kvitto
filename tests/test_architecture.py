"""Архитектурный тест: домен не зависит от внешних библиотек.

Правило зависимостей важнее любого отдельного класса: если в ``domain``
просочится ``sqlalchemy`` или ``fastapi``, границы слоёв перестают
существовать. Проверяем это AST-разбором импортов.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = PROJECT_ROOT / "kvitto" / "domain"

FORBIDDEN_ROOTS = {
    "fastapi",
    "starlette",
    "sqlalchemy",
    "pydantic",
    "alembic",
    "httpx",
    "requests",
}


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def test_domain_directory_exists():
    assert DOMAIN_DIR.is_dir(), "доменный слой должен существовать"


@pytest.mark.parametrize("module_path", sorted(DOMAIN_DIR.glob("*.py")), ids=lambda p: p.name)
def test_domain_module_has_no_framework_imports(module_path: Path):
    offenders = {
        module
        for module in _top_level_imports(module_path)
        if module.split(".")[0] in FORBIDDEN_ROOTS
    }
    assert not offenders, f"{module_path.name} импортирует внешние библиотеки: {offenders}"


def test_domain_only_imports_other_domain_modules():
    """Все импорты внутри kvitto из домена ведут только в kvitto.domain."""
    allowed_package = "kvitto.domain"
    for module_path in sorted(DOMAIN_DIR.glob("*.py")):
        for module in _top_level_imports(module_path):
            if module.startswith("kvitto") and not module.startswith(allowed_package):
                pytest.fail(f"{module_path.name} импортирует {module} — нарушена граница слоёв")
