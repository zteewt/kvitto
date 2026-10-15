"""API приёма платежей.

Слои (правило зависимостей — только внутрь):

    api ───────────► application ─────► domain
    infrastructure ───────────────────► domain

``domain`` — чистая предметная область: не знает про HTTP, БД и ORM.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
