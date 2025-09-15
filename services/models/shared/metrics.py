import time
import uuid
import json
import logging
from typing import Dict, Any, Optional, Callable
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.routing import APIRouter


class MetricsCollector:
    """Thread-safe in-memory collector for basic request metrics.

    Captures total request count, success/error counts, and total latency.
    Computes average latency on demand.
    * Intended as a temporary solution until full observability is added.
    """

    def __init__(self, *, service_start_time: float | None = None) -> None:
        self._lock = Lock()
        self._total_requests = 0
        self._success_count = 0
        self._error_count = 0
        self._total_latency_seconds = 0.0
        self._service_start_time = service_start_time or time.monotonic()

    def record(self, *, latency_seconds: float, success: bool) -> None:
        """Record a request metric."""
        with self._lock:
            self._total_requests += 1
            if success:
                self._success_count += 1
            else:
                self._error_count += 1
            self._total_latency_seconds += max(0.0, latency_seconds)

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of the metrics."""
        with self._lock:
            avg_latency_ms = (
                (self._total_latency_seconds / self._total_requests) * 1000.0
                if self._total_requests > 0
                else 0.0
            )
            uptime_seconds = max(0.0, time.monotonic() - self._service_start_time)
            return {
                "totalRequests": self._total_requests,
                "successful": self._success_count,
                "errors": self._error_count,
                "avgLatencyMs": avg_latency_ms,
                "uptimeSeconds": uptime_seconds,
            }


def setup_basic_metrics(
    app: FastAPI,
    *,
    model_id: str,
    service_logger: Optional[logging.Logger] = None,
    service_name: Optional[str] = None,
    metrics_path: str = "/metrics",
) -> MetricsCollector:
    """Attach a basic metrics middleware and GET /metrics endpoint to the app.

    - Emits structured JSON logs per request with requestId, latency, status, modelId
    - Tracks counts and average latency in-memory
    - Exposes metrics at `metrics_path`
    """
    logger = service_logger or logging.getLogger(service_name or app.title or __name__)
    collector = MetricsCollector()

    @app.middleware("http")
    async def _metrics_logging_middleware(request: Request, call_next: Callable):  # type: ignore[override]
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        method = request.method
        path = request.url.path
        start = time.monotonic()
        status_code = 500
        success = False

        try:
            response = await call_next(request)
            status_code = getattr(response, "status_code", 200)
            success = status_code < 400
        except Exception:
            # Treat as error; status_code will remain 500
            success = False
            raise
        finally:
            latency_seconds = max(0.0, time.monotonic() - start)
            collector.record(latency_seconds=latency_seconds, success=success)

            log_record = {
                "event": "request",
                "requestId": request_id,
                "method": method,
                "path": path,
                "status": status_code,
                "latencyMs": round(latency_seconds * 1000.0, 3),
                "modelId": model_id,
            }
            try:
                logger.info(json.dumps(log_record, separators=(",", ":")))
            except Exception:
                # Never fail the request on logging issues
                logger.debug("failed to emit structured log", exc_info=True)

        # Add request id to response headers on success path
        try:
            response.headers["x-request-id"] = request_id  # type: ignore[name-defined]
        except Exception:
            pass
        return response

    router = APIRouter()

    @router.get(metrics_path)
    async def _get_metrics() -> Dict[str, Any]:
        payload = collector.snapshot()
        # Include model id for context
        payload["modelId"] = model_id
        return payload

    app.include_router(router)
    return collector
