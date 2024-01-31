import json
from typing import Optional, List, Dict, Union, Mapping, Any, TypeVar

from pydantic import BaseModel, root_validator, validator

TGeoQuery = TypeVar("TGeoQuery")


class GeoQuery(BaseModel, extra="allow"):
    variable: Optional[Union[str, List[str]]]
    # TODO: Check how `time` is to be represented
    time: Optional[Union[Dict[str, str], Dict[str, List[str]]]]
    area: Optional[Dict[str, float]]
    location: Optional[Dict[str, Union[float, List[float]]]]
    vertical: Optional[Union[float, List[float], Dict[str, float]]]
    filters: Optional[Dict]
    format: Optional[str]
    format_args: Optional[Dict]

    # TODO: Check if we are going to allow the vertical coordinates inside both
    # `area`/`location` nad `vertical`

    @root_validator
    def area_locations_mutually_exclusive_validator(cls, query):
        if query["area"] is not None and query["location"] is not None:
            raise KeyError(
                "area and location couldn't be processed together, please use"
                " one of them"
            )
        return query

    @root_validator(pre=True)
    def build_filters(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "filters" in values:
            return values
        filters = {k: v for k, v in values.items() if k not in cls.__fields__}
        values = {k: v for k, v in values.items() if k in cls.__fields__}
        values["filters"] = filters
        return values

    @validator("vertical")
    def match_vertical_dict(cls, value):
        if isinstance(value, dict):
            assert "start" in value, "Missing 'start' key"
            assert "stop" in value, "Missing 'stop' key"
        return value

    def original_query_json(self):
        """Return the JSON representation of the original query submitted
        to the geokube-dds"""
        res = super().dict()
        res = dict(**res.pop("filters", {}), **res)
        # NOTE: skip empty values to make query representation
        # shorter and more elegant
        res = dict(filter(lambda item: item[1] is not None, res.items()))
        return json.dumps(res)

    @classmethod
    def parse(
        cls, load: TGeoQuery | dict | str | bytes | bytearray
    ) -> TGeoQuery:
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
