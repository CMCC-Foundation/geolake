"""Unit tests for `DDSAuthenticationBackend._manage_user_token_auth`.

Regression guard: the unknown-user and wrong-key cases used to surface as
HTTP 500 (AttributeError on a `None` user / HTTPException raised inside the
middleware). They must now raise `DDSAuthenticationError` with the right code.
"""
import pytest
from starlette.authentication import AuthCredentials

import exceptions as exc
from auth.backend import DDSAuthenticationBackend
from auth.models import DDSUser

VALID_UUID = "11111111-1111-4111-8111-111111111111"
UNKNOWN_UUID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def backend():
    return DDSAuthenticationBackend()


def test_unknown_user_raises_401(backend, fake_db):
    # fake_db is empty -> get_user_details returns None
    with pytest.raises(exc.DDSAuthenticationError) as excinfo:
        backend._manage_user_token_auth(f"{UNKNOWN_UUID}:whatever")
    assert excinfo.value.code == 401


def test_wrong_key_raises_401(backend, fake_db, make_user):
    fake_db[VALID_UUID] = make_user(api_key="rightkey")
    with pytest.raises(exc.DDSAuthenticationError) as excinfo:
        backend._manage_user_token_auth(f"{VALID_UUID}:wrongkey")
    assert excinfo.value.code == 401


def test_malformed_token_raises_400(backend, fake_db):
    with pytest.raises(exc.DDSAuthenticationError) as excinfo:
        backend._manage_user_token_auth("not-a-uuid:key")
    assert excinfo.value.code == 400


def test_valid_token_returns_credentials(backend, fake_db, make_user):
    fake_db[VALID_UUID] = make_user(api_key="rightkey", roles=["admin"])
    creds, user = backend._manage_user_token_auth(f"{VALID_UUID}:rightkey")
    assert isinstance(creds, AuthCredentials)
    assert "authenticated" in creds.scopes
    assert "admin" in creds.scopes
    assert isinstance(user, DDSUser)
    assert user.id == VALID_UUID
