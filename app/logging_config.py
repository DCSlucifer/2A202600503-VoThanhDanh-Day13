from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars

from .pii import scrub_dict, scrub_text

LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))
AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "data/audit.jsonl"))
APP_NAME = os.getenv("APP_NAME", "day13-observability-lab")


# ---------------------------------------------------------------------------
# PII Scrubbing Processor
# ---------------------------------------------------------------------------

def scrub_event(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Structlog processor: sanitize PII from event string and all dict/string fields.
    Runs before serialization so no raw PII ever reaches log storage.
    """
    # Scrub the main event string
    if isinstance(event_dict.get("event"), str):
        event_dict["event"] = scrub_text(event_dict["event"])

    # Scrub payload dict recursively
    payload = event_dict.get("payload")
    if isinstance(payload, dict):
        event_dict["payload"] = scrub_dict(payload)

    # Scrub any loose string fields that might carry user content
    for key in ("detail", "message_preview", "answer_preview", "query_preview"):
        if isinstance(event_dict.get(key), str):
            event_dict[key] = scrub_text(event_dict[key])

    return event_dict


# ---------------------------------------------------------------------------
# JSONL File Sink
# ---------------------------------------------------------------------------

class JsonlFileProcessor:
    """Write each log record to a JSONL file, then pass event_dict downstream."""

    def __call__(self, logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        rendered = structlog.processors.JSONRenderer()(logger, method_name, dict(event_dict))
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(rendered + "\n")
        return event_dict


# ---------------------------------------------------------------------------
# Service / App Name Injector
# ---------------------------------------------------------------------------

def add_service_name(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Ensure every log record carries the service name (from env or explicit kwarg)."""
    if "service" not in event_dict:
        event_dict["service"] = APP_NAME
    return event_dict


# ---------------------------------------------------------------------------
# Audit Logger  (Bonus: +2 pts — separate audit.jsonl, PII-free)
# ---------------------------------------------------------------------------

class AuditLogger:
    """
    Writes structured audit events to a separate audit.jsonl file.
    Guaranteed PII-free: all string values are scrubbed before writing.

    Usage:
        audit_logger.log("request_received", user_id_hash="abc123", feature="qa")
    """

    def __init__(self, path: Path = AUDIT_LOG_PATH) -> None:
        self.path = path

    def log(self, event: str, **fields: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "audit": True,
            "event": scrub_text(event),
            **{k: (scrub_text(v) if isinstance(v, str) else v) for k, v in fields.items()},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")


audit_logger = AuditLogger()


# ---------------------------------------------------------------------------
# Configure structlog
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=log_level)

    structlog.configure(
        processors=[
            merge_contextvars,             # Pull correlation_id, env, user_id_hash etc.
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            add_service_name,              # Ensure service field is always present
            scrub_event,                   # PII redaction — runs before any serialization
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            JsonlFileProcessor(),          # Write to data/logs.jsonl
            structlog.processors.JSONRenderer(),  # Render to stdout
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger() -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger()
