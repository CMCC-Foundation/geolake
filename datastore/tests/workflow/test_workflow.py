import pytest

# Integration: Workflow imports geokube (DataCube/Datastore) → run in-image.
pytest.importorskip("geokube")
pytestmark = pytest.mark.integration

from geoquery.task import TaskList  # noqa: E402
from workflow.workflow import Workflow  # noqa: E402


def test_workflow_from_tasklist_builds_graph():
    tl = TaskList.parse(
        [
            {
                "id": "s1",
                "op": "subset",
                "args": {
                    "dataset_id": "ds",
                    "product_id": "prod",
                    "query": {"variable": ["t2m"]},
                },
            }
        ]
    )
    wf = Workflow.from_tasklist(tl)
    assert len(wf) == 1
    wf.verify()  # a valid graph does not raise
    tasks = list(wf.traverse())
    assert [t.id for t in tasks] == ["s1"]


def test_workflow_verify_fails_on_undefined_dependency():
    tl = TaskList.parse(
        [
            {
                "id": "s1",
                "op": "subset",
                "args": {"dataset_id": "ds", "product_id": "prod", "query": {}},
            },
            {
                "id": "a1",
                "op": "average",
                "use": ["s1", "ghost"],  # `ghost` is not defined
                "args": {"dim": "time"},
            },
        ]
    )
    wf = Workflow.from_tasklist(tl)
    with pytest.raises(ValueError, match=r"task with id .ghost. is not defined"):
        wf.verify()
