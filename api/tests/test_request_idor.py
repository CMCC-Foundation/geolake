"""IDOR regression tests for the request endpoints (SEC-10).

Ownership is enforced at the datastore layer, which signals "exists but not
yours" with ``PermissionError`` and "missing" with ``IndexError``/``None``.
These tests verify the handlers translate those into 403 / RequestNotFound,
with ``DBManager`` mocked so no database is required.
"""
import importlib.util
import pathlib
import types

import pytest

import exceptions as exc
from dbmanager.dbmanager import RequestStatus

# Load the request handler module directly from its file, bypassing
# `endpoint_handlers/__init__.py` (which imports `dataset` and would initialize
# the Datastore / pull in geokube). This keeps these tests geokube-free, like
# the rest of the API suite which avoids importing `main`.
_HANDLER_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "app"
    / "endpoint_handlers"
    / "request.py"
)
_spec = importlib.util.spec_from_file_location(
    "geolake_request_handler_under_test", _HANDLER_PATH
)
request_handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(request_handler)


class _FakeDB:
    """Stand-in for DBManager whose method results are configured per test."""

    def __init__(self, behaviors):
        self._behaviors = behaviors

    def _resolve(self, name):
        assert name in self._behaviors, f"unexpected DBManager call: {name}"
        value = self._behaviors[name]
        if isinstance(value, BaseException):
            raise value
        return value

    def get_request_status_and_reason(self, request_id, user_id=None):
        return self._resolve("status")

    def get_request_details(self, request_id, user_id=None):
        return self._resolve("details")

    def get_download_details_for_request_id(self, request_id, user_id=None):
        return self._resolve("download")


@pytest.fixture
def patch_db(monkeypatch):
    def _patch(**behaviors):
        monkeypatch.setattr(
            request_handler, "DBManager", lambda: _FakeDB(behaviors)
        )

    return _patch


# --- GET /requests/{id}/status -------------------------------------------
def test_status_owned_returns_payload(patch_db):
    patch_db(status=(RequestStatus.DONE, None))
    assert request_handler.get_request_status(user_id="u", request_id=1) == {
        "status": "DONE",
        "fail_reason": None,
    }


def test_status_not_owned_raises_403(patch_db):
    patch_db(status=PermissionError("not owned"))
    with pytest.raises(exc.AuthorizationFailed) as excinfo:
        request_handler.get_request_status(user_id="u", request_id=1)
    assert excinfo.value.code == 403


def test_status_not_found_raises_request_not_found(patch_db):
    patch_db(status=IndexError("missing"))
    with pytest.raises(exc.RequestNotFound):
        request_handler.get_request_status(user_id="u", request_id=1)


# --- GET /requests/{id}/size ---------------------------------------------
def test_size_owned_returns_bytes(patch_db):
    request_obj = types.SimpleNamespace(
        download=types.SimpleNamespace(size_bytes=123),
        dataset="d",
        product="p",
    )
    patch_db(details=request_obj)
    assert (
        request_handler.get_request_resulting_size(request_id=1, user_id="u")
        == 123
    )


def test_size_not_owned_raises_403(patch_db):
    patch_db(details=PermissionError("not owned"))
    with pytest.raises(exc.AuthorizationFailed) as excinfo:
        request_handler.get_request_resulting_size(request_id=1, user_id="u")
    assert excinfo.value.code == 403


def test_size_not_found_raises_request_not_found(patch_db):
    patch_db(details=None)
    with pytest.raises(exc.RequestNotFound):
        request_handler.get_request_resulting_size(request_id=1, user_id="u")


# --- GET /requests/{id}/uri ----------------------------------------------
def test_uri_owned_returns_uri(patch_db):
    download_obj = types.SimpleNamespace(download_uri="/download/1")
    patch_db(download=download_obj)
    assert (
        request_handler.get_request_uri(request_id=1, user_id="u")
        == "/download/1"
    )


def test_uri_not_owned_raises_403(patch_db):
    patch_db(download=PermissionError("not owned"))
    with pytest.raises(exc.AuthorizationFailed) as excinfo:
        request_handler.get_request_uri(request_id=1, user_id="u")
    assert excinfo.value.code == 403


def test_uri_not_found_raises_request_not_found(patch_db):
    patch_db(download=IndexError("missing"))
    with pytest.raises(exc.RequestNotFound):
        request_handler.get_request_uri(request_id=1, user_id="u")
