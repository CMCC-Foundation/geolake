import json
from collections import Counter
from typing import Any, Optional, TypeVar

from pydantic import BaseModel, Field, validator

TWorkflow = TypeVar("TWorkflow")


class Task(BaseModel):
    id: str | int
    op: str
    use: Optional[list[str | int]] = Field(default_factory=list)
    args: Optional[dict[str, Any]] = Field(default_factory=dict)

    @validator("use", pre=True, always=True, each_item=False)
    def match_use(cls, v):
        if v is None:
            return []
        return v


class TaskList(BaseModel):
    tasks: list[Task]

    @validator("tasks")
    def match_unique_ids(cls, items):
        for id_value, id_count in Counter([item.id for item in items]).items():
            if id_count != 1:
                raise ValueError(f"duplicated key found: `{id_value}`")
        return items

    @classmethod
    def parse(
        cls,
        workflow: TWorkflow | dict | list[dict] | str | bytes | bytearray,
    ) -> TWorkflow:
        if isinstance(workflow, cls):
            return workflow
        if isinstance(workflow, (str | bytes | bytearray)):
            workflow = json.loads(workflow)
        if isinstance(workflow, list):
            return cls(tasks=workflow)
        elif isinstance(workflow, dict):
            return cls(**workflow)
        else:
            raise TypeError(
                f"`workflow` argument of type `{type(workflow).__name__}`"
                " cannot be safetly parsed to the `Workflow`"
            )

    @property
    def dataset_id(self):
        for task in self.tasks:
            if task.op == "subset":
                return task.args.get("dataset_id", "<unknown>")

    @property
    def product_id(self):
        for task in self.tasks:
            if task.op == "subset":
                return task.args.get("product_id", "<unknown>")
