"""Unit tests for `DDSAuthenticationBackend.get_authorization_scheme_param`.

Pure function: no DB, no middleware. Validates the token-format parsing.
"""
import pytest

import exceptions as exc
from auth.backend import DDSAuthenticationBackend

VALID_UUID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def backend():
    return DDSAuthenticationBackend()


def test_valid_token_is_split(backend):
    assert backend.get_authorization_scheme_param(
        f"{VALID_UUID}:secret"
    ) == (VALID_UUID, "secret")


@pytest.mark.parametrize("token", ["", "   ", None])
def test_empty_token_raises(backend, token):
    with pytest.raises(exc.EmptyUserTokenError):
        backend.get_authorization_scheme_param(token)


@pytest.mark.parametrize(
    "token",
    [
        "no-separator",            # missing ':'
        f"{VALID_UUID}:a:b",       # too many ':'
        "not-a-uuid:secret",       # user_id is not a UUID
    ],
)
def test_improper_token_raises(backend, token):
    with pytest.raises(exc.ImproperUserTokenError):
        backend.get_authorization_scheme_param(token)
