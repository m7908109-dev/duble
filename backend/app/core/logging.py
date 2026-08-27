"""Structured logging that NEVER leaks API keys.

Every log line is formatted for easy grep. We run all messages through a
redactor that masks anything that looks like a Gemini/OpenAI API key.
"""
from __future__ import annotations

import logging
import sys

from app.core.security import redact


class RedactingFormatter(logging.Formatter):
    """Log formatter that strips secret-looking substrings."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return redact(msg)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        RedactingFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Quiet noisy libs.
    for noisy in ("urllib3", "httpx", "httpcore", "openai", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
