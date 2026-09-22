import json
import logging
import time
import uuid

from fastapi import FastAPI, Request

logger = logging.getLogger("driver_leaderboard.http")


def configure_observability(app: FastAPI) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    @app.middleware("http")
    async def request_telemetry(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }
            )
        )
        return response
