"""
Structured logging with scrubbing filter.

HARD RULE (AGENTS.md #6): No customer code in logs, traces, error messages.
The scrubbing filter drops any field named: source, code, diff, prompt, completion.
"""
from __future__ import annotations

import logging
import structlog

from typing import Any

# Fields that must never appear in logs (customer code protection)
_SCRUBBED_FIELDS = frozenset({"source", "code", "diff", "prompt", "completion"})


def _scrub_dict_recursive(d: dict[str, Any]) -> dict[str, Any]:
    for field in list(d.keys()):
        if field.lower() in _SCRUBBED_FIELDS:
            del d[field]
        elif isinstance(d[field], dict):
            _scrub_dict_recursive(d[field])
    return d


def _scrub_event_dict(
    logger: logging.Logger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Remove sensitive fields from all log events recursively."""
    return _scrub_dict_recursive(event_dict)


def configure_logging(app_env: str = "local") -> None:
    """Configure structlog with JSON output and scrubbing."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _scrub_event_dict,
    ]

    if app_env == "local":
        # Human-friendly output for development
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )
    else:
        # JSON for staging/prod
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[return-value]
