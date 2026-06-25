"""IDOR/auth regression tests for the download handler (SEC-10 / SEC-11).

The `/download/...` routes now require authentication and verify ownership at
the datastore layer (PermissionError → 403, IndexError → RequestNotFound).
These tests exercise `endpoint_handlers/file.py` with `DBManager` mocked, so no
database (nor geokube) is required.
"""
import importlib.util
import os
import pathlib
import types

import pytest

import exceptions as exc
from dbmanager.dbmanager import RequestStatus

# Load the file handler module directly from its file, bypassing
# `endpoint_handlers/__init__.py` (which imports `dataset` and would initialize
# the Datastore / pull in geokube). Keeps these tests geokube-free.
_HANDLER_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "app"
    / "endpoint_handlers"
    / "file.py"
)
_spec = importlib.util.spec_from_file_location(
    "geolake_file_handler_under_test", _HANDLER_PATH
)
file_handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(file_handler)

from fastapi.responses import FileResponse  # noqa: E402


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

    def get_download_details_for_request_id(self, request_id, user_id=None):
        return self._resolve("download")


@pytest.fixture
def patch_db(monkeypatch):
    def _patch(**behaviors):
        monkeypatch.setattr(
            file_handler, "DBManager", lambda: _FakeDB(behaviors)
        )

    return _patch


def test_download_owned_done_returns_file(patch_db, monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda _p: True)
    download = types.SimpleNamespace(location_path="/downloads/1/result.nc")
    patch_db(status=(RequestStatus.DONE, None), download=download)
    result = file_handler.download_request_result(request_id=1, user_id="u")
    assert isinstance(result, FileResponse)
    assert result.path == "/downloads/1/result.nc"


def test_download_not_owned_raises_403(patch_db):
    patch_db(status=PermissionError("not owned"))
    with pytest.raises(exc.AuthorizationFailed) as excinfo:
        file_handler.download_request_result(request_id=1, user_id="u")
    assert excinfo.value.code == 403


def test_download_missing_raises_request_not_found(patch_db):
    patch_db(status=IndexError("missing"))
    with pytest.raises(exc.RequestNotFound):
        file_handler.download_request_result(request_id=1, user_id="u")


def test_download_not_done_raises_not_yet_accomplished(patch_db):
    patch_db(status=(RequestStatus.RUNNING, None))
    with pytest.raises(exc.RequestNotYetAccomplished):
        file_handler.download_request_result(request_id=1, user_id="u")
