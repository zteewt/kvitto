"""Точка входа.

Запуск в разработке:

    uvicorn kvitto.main:app --reload
"""

from __future__ import annotations

from kvitto.api.app import create_app

app = create_app()
