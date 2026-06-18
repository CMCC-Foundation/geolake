"""Lightweight, import-safe security helpers for request validation.

This module depends only on `exceptions` (and stdlib / fastapi.responses), so
the validation logic can be unit-tested in isolation without importing the full
application or the datastore. The fixes here back the findings tracked in
`SECURITY_ASSESSMENT.md` / `SECURITY_REMEDIATION.md`.
"""
from pathlib import Path

from fastapi.responses import JSONResponse

import exceptions as exc


def safe_join(base_dir: str, relative: str) -> str:
    """Join ``relative`` under ``base_dir`` blocking path traversal (SEC-1).

    The candidate path is resolved (neutralizing ``..`` and symlinks) and must
    stay within ``base_dir``. Absolute paths and traversal attempts raise a 400
    instead of allowing arbitrary file reads.
    """
    base = Path(base_dir).resolve()
    candidate = (base / relative).resolve()
    if candidate != base and base not in candidate.parents:
        raise exc.MalformedQueryParameterError(
            "Invalid file path: resolved outside the result directory"
        )
    return str(candidate)


def parse_bbox(bbox: str) -> dict:
    """Parse a ``minx,miny,maxx,maxy`` bbox string into an area dict (SEC-2).

    Malformed input (non-numeric or wrong cardinality) raises a 400 instead of
    bubbling up as ValueError/IndexError -> 500.
    """
    try:
        values = [float(x) for x in bbox.split(",")]
    except ValueError as err:
        raise exc.MalformedQueryParameterError(
            "bbox must be 4 comma-separated numbers"
        ) from err
    if len(values) != 4:
        raise exc.MalformedQueryParameterError(
            "bbox must contain exactly 4 values (west,south,east,north)"
        )
    return {
        "west": values[0],
        "south": values[1],
        "east": values[2],
        "north": values[3],
    }


def build_path_filters(product_info: dict, filters_vals: list[str]) -> dict:
    """Map path filter segments to their names from product metadata (SEC-3).

    A missing ``metadata.filters`` or more path segments than defined filters
    raise a 400 instead of KeyError/IndexError -> 500.
    """
    filters_keys = (product_info.get("metadata") or {}).get("filters")
    if not filters_keys:
        raise exc.MalformedQueryParameterError(
            "This product does not define path filters"
        )
    if len(filters_vals) > len(filters_keys):
        raise exc.MalformedQueryParameterError(
            f"Too many filter segments (expected at most {len(filters_keys)})"
        )
    return {
        filters_keys[i]["name"]: filters_vals[i]
        for i in range(len(filters_vals))
    }


def ensure_no_separator(payload: str, separator: str) -> str:
    """Reject a serialized payload containing the broker message separator (SEC-5).

    The worker frames messages by splitting on ``separator``; a payload that
    embeds it would corrupt the framing. Convert that into a clean 400.
    """
    if separator in payload:
        raise exc.MalformedQueryParameterError(
            "Query payload contains a reserved control character"
        )
    return payload


class BodySizeLimitMiddleware:
    """Reject requests whose ``Content-Length`` exceeds a limit, with 413 (SEC-4).

    The check happens before the body is read. ``Content-Length`` may be absent
    for chunked uploads, so this is defense-in-depth on top of a reverse-proxy
    limit (nginx ``client_max_body_size``) rather than a complete control.
    """

    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            for name, value in scope.get("headers", []):
                if name == b"content-length":
                    try:
                        too_large = int(value) > self.max_body_bytes
                    except ValueError:
                        too_large = False
                    if too_large:
                        response = JSONResponse(
                            status_code=413,
                            content={"detail": "Request body too large"},
                        )
                        await response(scope, receive, send)
                        return
                    break
        await self.app(scope, receive, send)
