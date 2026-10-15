"""Базовый декларативный класс ORM."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Общий декларативный базовый класс."""
