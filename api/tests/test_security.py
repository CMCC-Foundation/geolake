"""Regression tests for the security fixes (see SECURITY_REMEDIATION.md).

They exercise the import-safe helpers in `security.py` (SEC-1/2/3/5) and the
body-size middleware (SEC-4) without importing the full app or the datastore.
"""
import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import exceptions as exc
from security import (
    BodySizeLimitMiddleware,
    build_path_filters,
    ensure_no_separator,
    parse_bbox,
    safe_join,
)


# --- SEC-2: bbox ----------------------------------------------------------
def test_parse_bbox_valid():
    assert parse_bbox("1,2,3,4") == {
        "west": 1.0,
        "south": 2.0,
        "east": 3.0,
        "north": 4.0,
    }


@pytest.mark.parametrize("bad", ["foo,bar,baz,qux", "1,2,3", "1,2,3,4,5", ""])
def test_parse_bbox_malformed_raises_400(bad):
    with pytest.raises(exc.MalformedQueryParameterError) as excinfo:
        parse_bbox(bad)
    assert excinfo.value.code == 400


# --- SEC-3: path filters --------------------------------------------------
def test_build_path_filters_valid():
    product_info = {"metadata": {"filters": [{"name": "a"}, {"name": "b"}]}}
    assert build_path_filters(product_info, ["x"]) == {"a": "x"}
    assert build_path_filters(product_info, ["x", "y"]) == {"a": "x", "b": "y"}


@pytest.mark.parametrize("product_info", [{}, {"metadata": {}}, {"metadata": {"filters": []}}])
def test_build_path_filters_missing_metadata_raises_400(product_info):
    with pytest.raises(exc.MalformedQueryParameterError):
        build_path_filters(product_info, ["x"])


def test_build_path_filters_too_many_segments_raises_400():
    product_info = {"metadata": {"filters": [{"name": "a"}]}}
    with pytest.raises(exc.MalformedQueryParameterError):
        build_path_filters(product_info, ["x", "y"])


# --- SEC-1: safe_join -----------------------------------------------------
def test_safe_join_allows_contained_file(tmp_path):
    base = tmp_path / "result.zarr"
    base.mkdir()
    assert safe_join(str(base), "data") == str((base / "data").resolve())


@pytest.mark.parametrize(
    "evil", ["../secret", "../../etc/passwd", "/etc/passwd", "a/../../b"]
)
def test_safe_join_blocks_traversal(tmp_path, evil):
    base = tmp_path / "result.zarr"
    base.mkdir()
    with pytest.raises(exc.MalformedQueryParameterError):
        safe_join(str(base), evil)


# --- SEC-5: broker separator ---------------------------------------------
def test_ensure_no_separator_passes_clean_payload():
    assert ensure_no_separator('{"a": 1}', "\\") == '{"a": 1}'


def test_ensure_no_separator_rejects_separator():
    with pytest.raises(exc.MalformedQueryParameterError):
        ensure_no_separator('{"a": "x\\y"}', "\\")


# --- SEC-4: body-size middleware -----------------------------------------
def _client(max_bytes):
    async def ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", ok, methods=["POST"])])
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=max_bytes)
    return TestClient(app)


def test_body_under_limit_passes():
    resp = _client(max_bytes=100).post("/", content=b"x" * 10)
    assert resp.status_code == 200


def test_body_over_limit_returns_413():
    resp = _client(max_bytes=10).post("/", content=b"x" * 100)
    assert resp.status_code == 413
