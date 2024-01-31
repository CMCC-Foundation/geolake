"""Module with workflow definition."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .utils import find_value


class Task(BaseModel):
    """Single task model definition."""

    id: str | int
    op: str
    use: list[str | int] = Field(default_factory=list)
    args: dict[str, Any] = Field(default_factory=dict)


class Workflow(BaseModel):
    """Workflow model definition."""

    tasks: list[Task]
    dataset_id: str = "<undefined>"
    product_id: str = "<undefined>"

    @model_validator(mode="before")
    @classmethod
    def obtain_dataset_id(cls, values):
        """Get dataset_id and product_id from included tasks."""
        dataset_id = find_value(values, key="dataset_id", recursive=True)
        if not dataset_id:
            raise KeyError(
                "'dataset_id' key was missing. did you defined it for 'args'?"
            )
        product_id = find_value(values, key="product_id", recursive=True)
        if not product_id:
            raise KeyError(
                "'product_id' key was missing. did you defined it for 'args'?"
            )
        return values | {"dataset_id": dataset_id, "product_id": product_id}

    @field_validator("tasks", mode="after")
    @classmethod
    def match_unique_ids(cls, items):
        """Verify the IDs are uniqe."""
        for id_value, id_count in Counter([item.id for item in items]).items():
            if id_count != 1:
                raise ValueError(f"duplicated key found: `{id_value}`")
        return items

    @classmethod
    def parse(
        cls,
        workflow: Workflow | dict | list[dict] | str | bytes | bytearray,
    ) -> Workflow:
        """Parse to Workflow model."""
        if isinstance(workflow, cls):
            return workflow
        if isinstance(workflow, (str | bytes | bytearray)):
            workflow = json.loads(workflow)
        if isinstance(workflow, list):
            return cls(tasks=workflow)  # type: ignore[arg-type]
        if isinstance(workflow, dict):
            return cls(**workflow)
        raise TypeError(
            f"`workflow` argument of type `{type(workflow).__name__}`"
            " cannot be safetly parsed to the `Workflow`"
        )
