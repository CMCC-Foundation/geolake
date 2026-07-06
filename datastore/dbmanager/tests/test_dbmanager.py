"""Unit tests for the import-safe DBManager helpers.

These cover the pure functions backing the cross-component security fixes
(SEC-10 ownership comparison, SEC-16 credential masking) without a database.
"""
import uuid

from dbmanager.dbmanager import mask_db_url, same_user


# --- SEC-10: per-user ownership comparison --------------------------------
def test_same_user_matches_equal_uuids():
    uid = uuid.uuid4()
    assert same_user(uid, str(uid)) is True


def test_same_user_is_case_insensitive_for_uuids():
    uid = uuid.uuid4()
    assert same_user(str(uid).upper(), str(uid).lower()) is True


def test_same_user_rejects_different_uuids():
    assert same_user(uuid.uuid4(), uuid.uuid4()) is False


def test_same_user_handles_non_uuid_strings():
    assert same_user("alice", "alice") is True
    assert same_user("alice", "bob") is False


def test_same_user_handles_none():
    assert same_user(None, "alice") is False
    assert same_user(None, None) is True


# --- SEC-16: credential masking in logged connection URL ------------------
def test_mask_db_url_hides_password():
    url = "postgresql://dds_user:s3cr3t-p@ss@db-host:5432/geolake"
    masked = mask_db_url(url)
    assert "s3cr3t" not in masked
    assert masked == "postgresql://dds_user:***@db-host:5432/geolake"


def test_mask_db_url_is_idempotent():
    masked = mask_db_url("postgresql://u:p@h:5432/db")
    assert mask_db_url(masked) == "postgresql://u:***@h:5432/db"


def test_mask_db_url_without_credentials_is_unchanged():
    url = "postgresql://db-host:5432/geolake"
    assert mask_db_url(url) == url
