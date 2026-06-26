from __future__ import annotations

import logging

from pythonjsonlogger import jsonlogger

from app.config import settings
from app.core.context import correlation_fields

_configured = False


class _CorrelationFilter(logging.Filter):
    """Inject current correlation ids (request_id/task_id/agent_run_id) into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for k, v in correlation_fields().items():
            setattr(record, k, v)
        return True


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "ts", "levelname": "level"},
        )
    )
    handler.addFilter(_CorrelationFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL.upper())
    _configured = True
