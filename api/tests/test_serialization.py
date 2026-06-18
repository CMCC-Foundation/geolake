"""Regressione della migrazione pydantic v2: il publish dei messaggi in
`endpoint_handlers/dataset.py` usa `model_dump_json()` su GeoQuery/TaskList."""
import json

from geoquery.geoquery import GeoQuery
from geoquery.task import TaskList


def test_geoquery_model_dump_json():
    gq = GeoQuery(variable=["t2m"], location={"latitude": 1, "longitude": 2})
    data = json.loads(gq.model_dump_json())
    assert data["variable"] == ["t2m"]
    assert data["location"] == {"latitude": 1, "longitude": 2}


def test_tasklist_model_dump_json():
    tl = TaskList(tasks=[{"id": "0", "op": "subset"}])
    data = json.loads(tl.model_dump_json())
    assert data["tasks"][0]["id"] == "0"
    assert data["tasks"][0]["op"] == "subset"
