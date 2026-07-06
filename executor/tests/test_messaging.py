"""Tests for the broker message framing (SEC-5).

Messages are framed as a JSON envelope; these tests cover the round-trip for
both message types and the rejection of malformed envelopes.
"""
import json

import pytest

from messaging import Message, MessageType  # noqa: E402
from geoquery.geoquery import GeoQuery  # noqa: E402
from geoquery.task import TaskList  # noqa: E402


def _encode(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def test_query_message_parsing():
    gq = GeoQuery(variable=["t2m"], location={"latitude": 1.0, "longitude": 2.0})
    msg = Message(
        _encode(
            {
                "request_id": 42,
                "type": "query",
                "dataset_id": "era5",
                "product_id": "reanalysis",
                "content": gq.model_dump_json(),
            }
        )
    )
    assert msg.type is MessageType.QUERY
    # request_id is normalized to str even when the JSON envelope carries it as
    # an int, since downstream code builds download paths/filenames from it.
    assert msg.request_id == "42"
    assert isinstance(msg.request_id, str)
    assert msg.dataset_id == "era5"
    assert msg.product_id == "reanalysis"
    assert isinstance(msg.content, GeoQuery)
    assert msg.content.variable == ["t2m"]


def test_query_message_with_control_chars_in_content():
    # The old separator framing could be corrupted by such content; the JSON
    # envelope handles it transparently (SEC-5).
    gq = GeoQuery(variable=["t2m"], filters={"note": "a\\b\x1ec"})
    msg = Message(
        _encode(
            {
                "request_id": 1,
                "type": "query",
                "dataset_id": "d",
                "product_id": "p",
                "content": gq.model_dump_json(),
            }
        )
    )
    assert msg.content.filters == {"note": "a\\b\x1ec"}


def test_workflow_message_parsing():
    tl = TaskList(
        tasks=[
            {
                "id": "0",
                "op": "subset",
                "args": {"dataset_id": "d", "product_id": "p"},
            }
        ]
    )
    msg = Message(
        _encode(
            {
                "request_id": 7,
                "type": "workflow",
                "content": tl.model_dump_json(),
            }
        )
    )
    assert msg.type is MessageType.WORKFLOW
    assert isinstance(msg.content, TaskList)
    assert msg.dataset_id == "d"
    assert msg.product_id == "p"


def test_invalid_message_type_raises():
    with pytest.raises(ValueError):
        Message(_encode({"request_id": 1, "type": "not_a_type", "content": "x"}))


def test_non_json_message_raises():
    with pytest.raises(ValueError):
        Message(b"not-a-json-envelope")


def test_missing_request_id_raises():
    with pytest.raises(ValueError):
        Message(_encode({"type": "query", "content": "{}"}))


def test_query_missing_dataset_field_raises():
    with pytest.raises(ValueError):
        Message(_encode({"request_id": 1, "type": "query", "content": "{}"}))
