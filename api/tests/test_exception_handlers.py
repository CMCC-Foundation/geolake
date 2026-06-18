"""Integration tests for the global error handling, via Starlette's TestClient.

Exercises the REAL handlers (`error_handlers.register_error_handlers` /
`auth_on_error`) and the REAL authentication backend (with the DB boundary
mocked), without importing `main` (which would initialize the Datastore).
"""
import pytest
from fastapi import FastAPI, HTTPException, Request
from starlette.authentication import requires
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.testclient import TestClient

import exceptions as exc
from auth.backend import DDSAuthenticationBackend
from error_handlers import auth_on_error, register_error_handlers

VALID_UUID = "11111111-1111-4111-8111-111111111111"
UNKNOWN_UUID = "22222222-2222-4222-8222-222222222222"


def _build_app(backend):
    app = FastAPI()
    app.add_middleware(
        AuthenticationMiddleware, backend=backend, on_error=auth_on_error
    )
    register_error_handlers(app)

    @app.get("/public")
    async def public(request: Request):
        return {"scopes": list(request.auth.scopes)}

    @app.get("/protected")
    @requires(["authenticated"])
    async def protected(request: Request):
        return {"user": request.user.id}

    @app.get("/raise/dds")
    async def raise_dds(request: Request):
        raise exc.MissingDatasetError(dataset_id="ds")

    @app.get("/raise/authz")
    async def raise_authz(request: Request):
        raise exc.AuthorizationFailed("u")

    @app.get("/raise/boom")
    async def raise_boom(request: Request):
        raise ValueError("internal secret detail")

    @app.get("/raise/nofile")
    async def raise_nofile(request: Request):
        raise FileNotFoundError

    return app


@pytest.fixture
def client(fake_db, make_user):
    fake_db[VALID_UUID] = make_user(api_key="rightkey")
    app = _build_app(DDSAuthenticationBackend())
    return TestClient(app, raise_server_exceptions=False)


def test_anonymous_is_allowed_on_public(client):
    assert client.get("/public").status_code == 200


def test_protected_without_token_is_403(client):
    assert client.get("/protected").status_code == 403


@pytest.mark.parametrize(
    "token,expected",
    [
        ("not-a-uuid:key", 400),                 # malformed format
        ("   ", 400),                            # empty
        (f"{UNKNOWN_UUID}:whatever", 401),       # unknown user (was 500)
        (f"{VALID_UUID}:wrongkey", 401),         # wrong key (was 500)
    ],
)
def test_auth_errors_return_proper_codes(client, token, expected):
    resp = client.get("/public", headers={"User-Token": token})
    assert resp.status_code == expected
    assert "detail" in resp.json()


def test_valid_token_is_authenticated(client):
    resp = client.get(
        "/protected", headers={"User-Token": f"{VALID_UUID}:rightkey"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"user": VALID_UUID}


def test_dds_exception_maps_to_400(client):
    assert client.get("/raise/dds").status_code == 400


def test_authorization_failed_maps_to_403(client):
    assert client.get("/raise/authz").status_code == 403


def test_unhandled_exception_is_generic_500(client):
    resp = client.get("/raise/boom")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert "secret" not in resp.text  # no traceback / internal detail leak


def test_file_not_found_maps_to_404(client):
    assert client.get("/raise/nofile").status_code == 404


def test_raw_httpexception_in_middleware_would_be_500(fake_db):
    """Control: proves why DDSAuthenticationError + on_error is necessary.

    A raw HTTPException raised inside the AuthenticationMiddleware bypasses the
    exception handlers and surfaces as 500 (the original root cause).
    """

    class BadBackend(DDSAuthenticationBackend):
        def authenticate(self, conn):
            raise HTTPException(status_code=401, detail="bad")

    app = _build_app(BadBackend())
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/public", headers={"User-Token": "x"}).status_code == 500
