"""Tests for per-product capability enforcement at the API layer.

The exception-class tests import only `exceptions` (geokube-free) and run on the
bare runner. The handler-wiring tests import `endpoint_handlers.dataset`, which
instantiates `Datastore()` at import (pulling in geokube), so they are guarded
with `pytest.importorskip("geokube")` and only run in the geolake-datastore
image / CI. The deep enforcement logic itself is covered geokube-free in
`datastore/geoquery/tests/test_capabilities.py`.
"""
import pathlib

import pytest

import exceptions as exc


# --- exception classes (always run) --------------------------------------
def test_operation_not_supported_is_400():
    err = exc.OperationNotSupportedError(
        dataset_id="d", product_id="p", violations=["reason a", "reason b"]
    )
    assert err.code == 400
    assert "d.p" in err.msg
    assert "reason a; reason b" in err.msg


def test_endpoint_disabled_is_405():
    assert exc.EndpointDisabledError().code == 405


# --- handler wiring (image/CI only) --------------------------------------
@pytest.fixture
def dataset_handler(monkeypatch, tmp_path):
    pytest.importorskip("geokube")
    repo = pathlib.Path(__file__).resolve().parents[2]
    # `Datastore()` is created at module import; point it at a real catalog
    # file so the open succeeds (we mock `product_metadata` per test anyway).
    monkeypatch.setenv(
        "CATALOG_PATH",
        str(repo / "drivers" / "tests" / "resources" / "synthetic_catalog.yaml"),
    )
    monkeypatch.setenv("CACHE_PATH", str(tmp_path))
    from endpoint_handlers import dataset as dataset_handler

    return dataset_handler


def _geoquery():
    from geoquery.geoquery import GeoQuery

    return GeoQuery


def test_enforce_capabilities_rejects_disallowed(dataset_handler, monkeypatch):
    GeoQuery = _geoquery()
    monkeypatch.setattr(
        dataset_handler.data_store,
        "product_metadata",
        lambda d, p: {"capabilities": {"spatial_subset": False}},
    )
    with pytest.raises(exc.OperationNotSupportedError) as excinfo:
        dataset_handler._enforce_capabilities(
            "d",
            "p",
            GeoQuery(area={"north": 1, "south": 0, "east": 1, "west": 0}),
        )
    assert excinfo.value.code == 400


def test_enforce_capabilities_allows_permissive(dataset_handler, monkeypatch):
    GeoQuery = _geoquery()
    monkeypatch.setattr(
        dataset_handler.data_store, "product_metadata", lambda d, p: {}
    )
    # Permissive (no capabilities block) -> no exception.
    dataset_handler._enforce_capabilities(
        "d", "p", GeoQuery(variable=["t2m"])
    )


def test_enforce_capabilities_runs_even_when_estimate_disabled(
    dataset_handler, monkeypatch
):
    # `sentinel-2` has estimation disabled (_is_etimate_enabled), but capability
    # enforcement must still run for it.
    GeoQuery = _geoquery()
    assert dataset_handler._is_etimate_enabled("sentinel-2", "p") is False
    monkeypatch.setattr(
        dataset_handler.data_store,
        "product_metadata",
        lambda d, p: {"capabilities": {"temporal_subset": False}},
    )
    with pytest.raises(exc.OperationNotSupportedError):
        dataset_handler._enforce_capabilities(
            "sentinel-2",
            "p",
            GeoQuery(time={"start": "2020-01-01", "stop": "2020-02-01"}),
        )
