import json
from typing import Optional, List, Dict, Union, Mapping, Any, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

TGeoQuery = TypeVar("TGeoQuery")


class GeoQuery(BaseModel):
    model_config = ConfigDict(extra="allow")

    variable: Optional[Union[str, List[str]]] = None
    # TODO: Check how `time` is to be represented
    resample: Optional[Dict[str, str]] = None
    time: Optional[Union[Dict[str, str], Dict[str, List[str]]]] = None
    area: Optional[Dict[str, float]] = None
    location: Optional[Dict[str, Union[float, List[float]]]] = None
    vertical: Optional[Union[float, List[float], Dict[str, float]]] = None
    filters: Optional[Dict] = None
    format: Optional[str] = None
    format_args: Optional[Dict] = None
    regrid: Optional[str] = None

    # TODO: Check if we are going to allow the vertical coordinates inside both
    # `area`/`location` nad `vertical`

    @model_validator(mode="before")
    @classmethod
    def area_locations_mutually_exclusive_validator(cls, query):
        if isinstance(query, dict) and "area" in query and "location" in query:
            if query["area"] is not None and query["location"] is not None:
                raise KeyError(
                    "area and location couldn't be processed together,"
                    " please use one of them"
                )
        return query

    @model_validator(mode="before")
    @classmethod
    def build_filters(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        if "filters" in values:
            return values
        filters = {k: v for k, v in values.items() if k not in cls.model_fields}
        values = {k: v for k, v in values.items() if k in cls.model_fields}
        values["filters"] = filters
        return values

    @field_validator("vertical")
    @classmethod
    def match_vertical_dict(cls, value):
        if isinstance(value, dict):
            assert "start" in value, "Missing 'start' key"
            assert "stop" in value, "Missing 'stop' key"
        return value

    def original_query_json(self):
        """Return the JSON representation of the original query submitted
        to the geokube-dds"""
        res = self.model_dump()
        res = dict(**res.pop("filters", {}), **res)
        # NOTE: skip empty values to make query representation
        # shorter and more elegant
        res = dict(filter(lambda item: item[1] is not None, res.items()))
        return json.dumps(res)

    @classmethod
    def parse(
        cls, load: "TGeoQuery | dict | str | bytes | bytearray"
    ) -> "TGeoQuery":
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
