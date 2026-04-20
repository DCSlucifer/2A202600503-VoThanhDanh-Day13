from __future__ import annotations

import os
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Injects a correlation ID into every request and binds it to structlog contextvars.

    - Reads x-request-id from incoming headers (for upstream propagation).
    - Falls back to generating a new req-<8-hex> ID.
    - Clears contextvars before each request to prevent cross-request leakage.
    - Sets x-request-id and x-response-time-ms on the response.
    """

    async def dispatch(self, request: Request, call_next):
        # CRITICAL: clear contextvars to prevent leakage between concurrent requests
        clear_contextvars()

        incoming = request.headers.get("x-request-id", "").strip()
        if incoming and _is_valid_correlation_id(incoming):
            correlation_id = incoming
        else:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"

        # Bind to structlog contextvars — propagates to all log calls in this request
        bind_contextvars(
            correlation_id=correlation_id,
            env=os.getenv("APP_ENV", "dev"),
        )

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = str(elapsed_ms)

        return response


def _is_valid_correlation_id(value: str) -> bool:
    """Accept req-<8hex> format only to prevent header injection."""
    if not value.startswith("req-"):
        return False
    suffix = value[4:]
    return len(suffix) == 8 and all(c in "0123456789abcdef" for c in suffix.lower())
