"""Centralized error handling for the geolake API.

This module is intentionally lightweight (it depends only on FastAPI/Starlette
and the local `exceptions` module), so it can be imported and unit-tested
without triggering the heavy import-time side effects of `main.py`
(e.g. `Datastore()` initialization in the endpoint handlers).
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.requests import HTTPConnection

from utils.api_logging import get_dds_logger
import exceptions as exc

# geokube is a heavy, optional dependency: present in the running API image but
# not in the geokube-free unit-test env. Import it guardedly so this module stays
# importable/unit-testable without geokube; the CacheNotExist handler below is
# only registered when geokube is actually available.
try:
    from geokube.core.errs import CacheNotExist
except Exception:  # pragma: no cover - exercised only in the geokube-free env
    CacheNotExist = None

logger = get_dds_logger(__name__)


def auth_on_error(conn: HTTPConnection, err: Exception) -> JSONResponse:
    """Convert authentication errors raised inside the middleware into proper
    HTTP responses (400/401/403).

    Exceptions raised by the authentication backend bypass FastAPI's exception
    handlers (those live in the inner `ExceptionMiddleware`), so they must be
    handled here, at the middleware boundary, to avoid surfacing as 500.
    """
    if isinstance(err, exc.DDSAuthenticationError):
        code, detail = err.code, err.detail
    else:
        code, detail = 401, "Authentication failed"
    logger.info("authentication error: %s", detail)
    return JSONResponse(status_code=code, content={"detail": detail})


def register_error_handlers(app) -> None:
    """Register the global exception handlers on the given FastAPI app."""

    @app.exception_handler(exc.BaseDDSException)
    async def _dds_exception_handler(request: Request, err: exc.BaseDDSException):
        """Serialize any DDS exception into its proper HTTP status code + detail."""
        return JSONResponse(status_code=err.code, content={"detail": err.msg})

    @app.exception_handler(FileNotFoundError)
    async def _file_not_found_handler(request: Request, err: FileNotFoundError):
        """Map a missing result file to a 404 response."""
        return JSONResponse(
            status_code=404, content={"detail": "File was not found!"}
        )

    if CacheNotExist is not None:

        @app.exception_handler(CacheNotExist)
        async def _cache_not_built_handler(request: Request, err):
            """A `metadata_caching` product whose kerchunk cache has not been
            built yet. Temporary condition -> 503 (the catalog build job
            publishes the cache out-of-band); the listing also hides it."""
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Product temporarily unavailable"
                    " (metadata cache not built yet)"
                },
            )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, err: Exception):
        """Catch-all handler: log the full traceback server-side and return a
        generic, non-leaky 500 envelope so internal details are never exposed."""
        logger.error(
            "unhandled exception on %s %s",
            request.method,
            request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
