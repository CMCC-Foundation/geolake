import json
from typing import Optional, List, Dict, Union, Mapping, Any, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

TGeoQuery = TypeVar("TGeoQuery")

# Bounds for the free-form `filters` mapping (SEC-15). They keep an abusive or
# accidentally huge payload from being forwarded unchecked to the datastore /
# broker, while leaving normal path/extra filters (a handful of scalars) intact.
MAX_FILTERS = 64
MAX_FILTER_VALUE_LEN = 1024
MAX_FILTER_LIST_LEN = 512

# Scalar types accepted as filter values (bool is a subclass of int).
_FILTER_SCALARS = (str, int, float, bool)


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
        # Always fold any extra (non-model) field into `filters` and merge it
        # with an explicitly-provided `filters` mapping. This guarantees no
        # extra field escapes validation by living in `__pydantic_extra__`
        # (SEC-15); explicit filters take precedence on key clashes.
        explicit = values.get("filters") or {}
        if not isinstance(explicit, dict):
            # Let the field validator below reject a non-mapping `filters`.
            return values
        extra = {
            k: v for k, v in values.items() if k not in cls.model_fields
        }
        known = {k: v for k, v in values.items() if k in cls.model_fields}
        known["filters"] = {**extra, **explicit}
        return known

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, value):
        """Constrain the free-form `filters` mapping (SEC-15).

        Keys must be strings; values must be scalars or *flat* lists of
        scalars (no nested objects/dicts), bounded in number and size.
        """
        if value is None:
            return value
        if not isinstance(value, dict):
            raise ValueError("`filters` must be a mapping")
        if len(value) > MAX_FILTERS:
            raise ValueError(
                f"too many filters (max {MAX_FILTERS})"
            )

        def _check_scalar(item):
            # `bool` passes via `int`; reject dicts and other objects.
            if item is not None and not isinstance(item, _FILTER_SCALARS):
                raise ValueError(
                    "filter values must be scalars or flat lists of scalars"
                )
            if isinstance(item, str) and len(item) > MAX_FILTER_VALUE_LEN:
                raise ValueError("filter value is too long")

        for key, val in value.items():
            if not isinstance(key, str):
                raise ValueError("filter keys must be strings")
            if isinstance(val, (list, tuple)):
                if len(val) > MAX_FILTER_LIST_LEN:
                    raise ValueError("filter list is too long")
                for item in val:
                    _check_scalar(item)
            else:
                _check_scalar(val)
        return value

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
