import pytest

from geoquery.geoquery import GeoQuery


def test_query_no_attrs():
    query_dict = {
        "variable": ["wind_speed"],
        "location": {"latitude": 10, "longitude": 25},
        "time": {"start": "2012-01-01", "stop": "2012-01-15"},
    }
    query = GeoQuery(**query_dict)
    assert query.variable == ["wind_speed"]
    assert query.location == {"latitude": 10, "longitude": 25}
    assert query.time == {"start": "2012-01-01", "stop": "2012-01-15"}


def test_raise_when_location_and_area():
    query_dict = {
        "area": {
            "north": 46.804443359375,
            "south": 43,
            "east": 41.96259307861328,
            "west": 38,
        },
        "location": {"latitude": 10, "longitude": 25},
    }
    with pytest.raises(
        KeyError, match=r"area and location couldn't be processed together*"
    ):
        _ = GeoQuery(**query_dict)


def test_attrs_parsing():
    query_dict = {
        "resolution": "0.1",
    }
    query = GeoQuery(**query_dict)
    assert "resolution" not in query.__dict__
    assert query.filters["resolution"] == "0.1"
    assert len(query.__dict__) == 6


def test_convert_extra_to_filters():
    query_dict = {
        "resolution": "0.1",
        "version": "5",
        "location": {"latitude": 10, "longitude": 25},
    }
    query = GeoQuery(**query_dict)
    assert len(query.__dict__) == 6
    assert query.location == {"latitude": 10, "longitude": 25}
    assert isinstance(query.filters, dict)
    assert query.filters == {"resolution": "0.1", "version": "5"}


def test_emtpy_filters():
    query_dict = {
        "variable": ["wind_speed"],
        "location": {"latitude": 10, "longitude": 25},
        "time": {"start": "2012-01-01", "stop": "2012-01-15"},
    }
    query = GeoQuery(**query_dict)
    assert isinstance(query.filters, dict)
    assert len(query.filters) == 0
