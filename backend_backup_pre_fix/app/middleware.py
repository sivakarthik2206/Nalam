"""Custom middlewares for error handling and request logging in Nalam API."""

import logging
import time
import traceback
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import SQLAlchemyError
import httpx

logger = logging.getLogger("nalam.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming HTTP requests, response status, and duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        method = request.method
        path = request.url.path
        query = str(request.url.query)
        full_path = f"{path}?{query}" if query else path

        logger.info(f"--> {method} {full_path}")

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"<-- {method} {full_path} {response.status_code} ({duration_ms:.2f}ms)")
            response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"<-- {method} {full_path} FAILED after {duration_ms:.2f}ms: {exc}")
            raise exc


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and maps them to clean HTTP error responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except SQLAlchemyError as exc:
            logger.error(f"Database error on {request.method} {request.url.path}: {exc}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Database Service Unavailable",
                    "detail": "An error occurred while connecting or executing against the database.",
                    "message": str(exc),
                },
            )
        except httpx.HTTPError as exc:
            logger.error(f"Upstream HTTP error on {request.method} {request.url.path}: {exc}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=502,
                content={
                    "error": "Upstream Service Error",
                    "detail": "An external API dependency (e.g. Bolna or Twilio) returned an error or timed out.",
                    "message": str(exc),
                },
            )
        except Exception as exc:
            logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "detail": "An unexpected error occurred while processing the request.",
                    "message": str(exc),
                },
            )
