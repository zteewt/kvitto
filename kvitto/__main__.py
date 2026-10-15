"""Запуск сервиса без указания команды uvicorn.

    python -m kvitto

Эквивалент ``uvicorn kvitto.main:app --host 127.0.0.1 --port 8000``.
Для разработки удобнее uvicorn с ``--reload``.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "kvitto.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
