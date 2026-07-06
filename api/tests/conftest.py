"""Shared fixtures for the geolake API test-suite.

No ``sys.path`` / ``sys.modules`` manipulation: the API modules resolve via the
editable install (``pip install -e ".[dev]"``) and the datastore stack
(``dbmanager``, ``utils``, …) is provided by the runtime environment — the
``geolake-datastore`` base image locally/CI. Boundaries (DB, broker) are mocked
with ``monkeypatch`` on the imported symbols.
"""
import types

import pytest

from auth import backend as auth_backend


@pytest.fixture
def make_user():
    """Factory for a minimal user DTO compatible with the auth backend."""

    def _make(api_key, roles=()):
        return types.SimpleNamespace(
            api_key=api_key,
            roles=[types.SimpleNamespace(role_name=name) for name in roles],
        )

    return _make


@pytest.fixture
def fake_db(monkeypatch):
    """Replace the DB boundary with an in-memory user store.

    Returns a dict (``user_id -> DTO``) the test can populate. ``DBManager()``
    in the backend is swapped for a fake class, so no real database (nor the
    ``POSTGRES_*`` environment) is required.
    """
    users: dict = {}

    class FakeDBManager:
        def get_user_details(self, user_id):
            return users.get(user_id)

    monkeypatch.setattr(auth_backend, "DBManager", FakeDBManager)
    return users
