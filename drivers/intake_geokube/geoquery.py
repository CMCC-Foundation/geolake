import json
from typing import Optional, List, Dict, Union, Any, TypeVar

from pydantic import BaseModel, root_validator, validator

TGeoQuery = TypeVar("TGeoQuery")

def _maybe_convert_dict_slice_to_slice(dict_vals):
    if "start" in dict_vals or "stop" in dict_vals:
        return slice(
            dict_vals.get("start"),
            dict_vals.get("stop"),
            dict_vals.get("step"),
        )
    return dict_vals     

class _GeoQueryJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, slice):
            return {
                "start": obj.start,
                "stop": obj.stop,
                "step": obj.step
            }
        return json.JSONEncoder.default(self, obj)


class GeoQuery(BaseModel):
    variable: Optional[Union[str, List[str]]]
    # TODO: Check how `time` is to be represented
    time: Optional[Union[Dict[str, str | None], Dict[str, List[str]]]]
    area: Optional[Dict[str, float]]
    location: Optional[Dict[str, Union[float, List[float]]]]
    vertical: Optional[Union[float, List[float], Dict[str, float]]]
    filters: Optional[Dict]
    format: Optional[str]
    format_args: Optional[Dict]

    class Config:
        extra = "allow"
        json_encoders = {slice: lambda s: {
                "start": s.start,
                "stop": s.stop,
                "step": s.step
            }}    

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
        filters = {k: _maybe_convert_dict_slice_to_slice(v) for k, v in values.items() if k not in cls.__fields__}
        values = {k: v for k, v in values.items() if k in cls.__fields__}
        values["filters"] = filters
        return values

    @validator("time", always=True)
    def match_time_dict(cls, value):
        if isinstance(value, dict):
            assert any([k in value for k in ("start", "stop", "year", "month", "day", "hour")]), "Missing dictionary key"
            if "start" in value or "stop" in value:
                return _maybe_convert_dict_slice_to_slice(value)
        return value    
    

    @validator("vertical", always=True)
    def match_vertical_dict(cls, value):
        if isinstance(value, dict):
            assert "start" in value, "Missing 'start' key"
            assert "stop" in value, "Missing 'stop' key"
            return _maybe_convert_dict_slice_to_slice(value)
        return value

    def original_query_json(self):
        """Return the JSON representation of the original query submitted
        to the geokube-dds"""
        res = super().dict()
        res = dict(**res.pop("filters", {}), **res)
        # NOTE: skip empty values to make query representation
        # shorter and more elegant
        res = dict(filter(lambda item: item[1] is not None, res.items()))
        return json.dumps(res, cls=_GeoQueryJSONEncoder)
    
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
