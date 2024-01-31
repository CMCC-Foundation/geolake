"""Module with GeoQuery definition."""

from __future__ import annotations

import json
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

from .types import BoundingBoxDict, SliceQuery, TimeComboDict
from .utils import maybe_dict_to_slice, slice_to_dict


class GeoQuery(BaseModel, extra="allow"):
    """GeoQuery definition class."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    variable: list[str] | None = None
    time: SliceQuery | TimeComboDict | None = None
    area: BoundingBoxDict | None = None
    location: dict[str, float | list[float]] | None = None
    vertical: SliceQuery | float | list[float] | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    format: str | None = None
    format_args: dict[str, Any] | None = None

    @field_serializer("time")
    def serialize_time(self, time: SliceQuery | TimeComboDict | None, _info):
        """Serialize time."""
        if isinstance(time, slice):
            return slice_to_dict(time)
        return time

    @model_validator(mode="after")
    @classmethod
    def area_locations_mutually_exclusive_validator(cls, query):
        """Assert 'locations' and 'area' are not passed at once."""
        if query.area is not None and query.location is not None:
            raise KeyError(
                "area and location couldn't be processed together, please use"
                " one of them"
            )
        return query

    @model_validator(mode="before")
    @classmethod
    def build_filters(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Build filters based on extra arguments."""
        if "filters" in values:
            return values
        filters = {}
        fields = {}
        for k in values.keys():
            if k in cls.model_fields:
                fields[k] = values[k]
                continue
            if isinstance(values[k], dict):
                values[k] = maybe_dict_to_slice(values[k])
            filters[k] = values[k]
        fields["filters"] = filters
        return fields

    def model_dump_original(self, skip_empty: bool = True) -> dict:
        """Return the JSON representation of the original query."""
        res = super().model_dump()
        res = {**res.pop("filters", {}), **res}
        if skip_empty:
            res = dict(filter(lambda item: item[1] is not None, res.items()))
        return res

    @classmethod
    def parse(
        cls, load: "GeoQuery" | dict | str | bytes | bytearray
    ) -> "GeoQuery":
        """Parse load to GeoQuery instance."""
        if isinstance(load, cls):
            return load
        if isinstance(load, (str, bytes, bytearray)):
            load = json.loads(load)
        if isinstance(load, dict):
            load = GeoQuery(**load)
        else:
            raise TypeError(
                f"type of the `load` argument ({type(load).__name__}) is not"
                " supported!"
            )
        return load
