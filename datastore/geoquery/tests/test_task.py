import pytest

from geoquery.task import Task, TaskList


def test_task_defaults():
    t = Task(id="1", op="subset")
    assert t.use == []
    assert t.args == {}


def test_task_use_none_becomes_empty_list():
    # field_validator(mode="before") must convert None → []
    t = Task(id="1", op="subset", use=None)
    assert t.use == []


def test_tasklist_rejects_duplicate_ids():
    with pytest.raises(ValueError, match=r"duplicated key found"):
        TaskList(tasks=[{"id": "a", "op": "subset"}, {"id": "a", "op": "resample"}])


def test_tasklist_parse_from_list():
    tl = TaskList.parse(
        [{"id": "a", "op": "subset", "args": {"dataset_id": "d", "product_id": "p"}}]
    )
    assert isinstance(tl, TaskList)
    assert tl.dataset_id == "d"
    assert tl.product_id == "p"


def test_tasklist_parse_from_json_str():
    tl = TaskList.parse('[{"id": "a", "op": "subset"}]')
    assert len(tl.tasks) == 1
    assert tl.tasks[0].id == "a"
