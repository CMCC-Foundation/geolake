import os

import pytest

SEP = os.environ["MESSAGE_SEPARATOR"]

from messaging import Message, MessageType  # noqa: E402
from geoquery.geoquery import GeoQuery  # noqa: E402
from geoquery.task import TaskList  # noqa: E402


def _encode(*parts):
    return SEP.join(parts).encode()


def test_query_message_parsing():
    gq = GeoQuery(variable=["t2m"], location={"latitude": 1.0, "longitude": 2.0})
    msg = Message(_encode("42", "query", "era5", "reanalysis", gq.model_dump_json()))
    assert msg.type is MessageType.QUERY
    assert msg.request_id == "42"
    assert msg.dataset_id == "era5"
    assert msg.product_id == "reanalysis"
    assert isinstance(msg.content, GeoQuery)
    assert msg.content.variable == ["t2m"]


def test_workflow_message_parsing():
    tl = TaskList(
        tasks=[{"id": "0", "op": "subset", "args": {"dataset_id": "d", "product_id": "p"}}]
    )
    msg = Message(_encode("7", "workflow", tl.model_dump_json()))
    assert msg.type is MessageType.WORKFLOW
    assert isinstance(msg.content, TaskList)
    assert msg.dataset_id == "d"
    assert msg.product_id == "p"


def test_invalid_message_type_raises():
    with pytest.raises(ValueError):
        Message(_encode("1", "not_a_type", "x"))


def test_malformed_query_message_raises():
    with pytest.raises(AssertionError):
        Message(_encode("1", "query", "only_one_field"))
