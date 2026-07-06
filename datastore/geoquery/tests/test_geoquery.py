import json

import pytest
from pydantic import ValidationError

from geoquery.geoquery import (
    GeoQuery,
    MAX_FILTERS,
    MAX_FILTER_VALUE_LEN,
    MAX_FILTER_LIST_LEN,
)


def test_query_no_attrs():
    query = GeoQuery(
        variable=["wind_speed"],
        location={"latitude": 10, "longitude": 25},
        time={"start": "2012-01-01", "stop": "2012-01-15"},
    )
    assert query.variable == ["wind_speed"]
    assert query.location == {"latitude": 10, "longitude": 25}
    assert query.time == {"start": "2012-01-01", "stop": "2012-01-15"}


def test_format_optional_defaults_to_none():
    # pydantic v2 regression: `Optional[str]` without a default would be REQUIRED.
    query = GeoQuery(variable=["t2m"])
    assert query.format is None


def test_raise_when_location_and_area():
    with pytest.raises(
        KeyError, match=r"area and location couldn't be processed together*"
    ):
        GeoQuery(
            area={"north": 46.8, "south": 43, "east": 41.9, "west": 38},
            location={"latitude": 10, "longitude": 25},
        )


def test_attrs_parsing():
    query = GeoQuery(resolution="0.1")
    assert query.filters == {"resolution": "0.1"}
    assert not hasattr(query, "resolution")


def test_convert_extra_to_filters():
    query = GeoQuery(
        resolution="0.1",
        version="5",
        location={"latitude": 10, "longitude": 25},
    )
    assert query.location == {"latitude": 10, "longitude": 25}
    assert query.filters == {"resolution": "0.1", "version": "5"}


def test_empty_filters():
    query = GeoQuery(
        variable=["wind_speed"],
        location={"latitude": 10, "longitude": 25},
        time={"start": "2012-01-01", "stop": "2012-01-15"},
    )
    assert isinstance(query.filters, dict)
    assert len(query.filters) == 0


def test_vertical_dict_requires_start_and_stop():
    with pytest.raises(ValidationError):
        GeoQuery(vertical={"start": 1.0})  # 'stop' is missing


def test_original_query_json_flattens_filters():
    query = GeoQuery(variable=["t2m"], resolution="0.1")
    data = json.loads(query.original_query_json())
    assert data["variable"] == ["t2m"]
    assert data["resolution"] == "0.1"  # extra promoted to top-level
    assert "filters" not in data  # filters emptied/flattened


# --- SEC-15: filters validation ------------------------------------------
def test_filters_accept_scalars_and_flat_lists():
    query = GeoQuery(
        filters={"resolution": "0.1", "level": 5, "ratio": 0.5, "members": [1, 2, "a"]}
    )
    assert query.filters["members"] == [1, 2, "a"]


def test_explicit_and_extra_filters_are_merged():
    # extra (non-model) field is folded into the explicit `filters` mapping.
    query = GeoQuery(resolution="0.1", filters={"version": "5"})
    assert query.filters == {"resolution": "0.1", "version": "5"}


def test_filters_reject_nested_dict():
    with pytest.raises(ValidationError):
        GeoQuery(filters={"bad": {"nested": "value"}})


def test_filters_reject_nested_dict_inside_list():
    with pytest.raises(ValidationError):
        GeoQuery(filters={"bad": [{"nested": "value"}]})


def test_filters_reject_too_many_keys():
    too_many = {str(i): i for i in range(MAX_FILTERS + 1)}
    with pytest.raises(ValidationError):
        GeoQuery(filters=too_many)


def test_filters_reject_overlong_value():
    with pytest.raises(ValidationError):
        GeoQuery(filters={"k": "x" * (MAX_FILTER_VALUE_LEN + 1)})


def test_filters_reject_overlong_list():
    with pytest.raises(ValidationError):
        GeoQuery(filters={"k": list(range(MAX_FILTER_LIST_LEN + 1))})
