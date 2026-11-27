"""Small, dependency-free HTTP hardening helpers for the demo service."""

from collections import defaultdict, deque
import os
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .entities import redact


class SecurityMiddleware(BaseHTTPMiddleware):
    """Apply browser headers, a bounded request rate, and safe error responses."""

    def __init__(self, app):
        super().__init__(app)
        self.limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "1000"))
        self.requests = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        now = time.monotonic()
        address = request.client.host if request.client else "unknown"
        bucket = self.requests[address]
        while bucket and now - bucket[0] >= 60:
            bucket.popleft()
        if len(bucket) >= self.limit:
            response = JSONResponse({"detail": "Too many requests"}, status_code=429)
        else:
            bucket.append(now)
            try:
                response = await call_next(request)
            except Exception:
                response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        response.headers.update(
            {
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "SAMEORIGIN",
                "Referrer-Policy": "no-referrer",
                "Permissions-Policy": "microphone=(self), camera=()",
                "Cache-Control": "no-store" if request.url.path.startswith("/v1/") else "no-cache",
            }
        )
        return response


def masked_log_text(value: str) -> str:
    """Redact secrets and account-like digit strings before writing logs."""
    return redact(value)
