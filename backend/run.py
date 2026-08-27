"""Convenience launcher: `python run.py`."""
from __future__ import annotations

import os

import uvicorn

from app.core.config import settings


def main() -> None:
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=1,
        reload=False,
    )


if __name__ == "__main__":
    main()
