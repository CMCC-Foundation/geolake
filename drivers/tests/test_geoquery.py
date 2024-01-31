from unittest import mock

import pytest

from intake_geokube.queries.geoquery import GeoQuery


class TestGeoQuery:
    def test_pass_time_as_combo(self):
        query = GeoQuery(
            time={
                "year": ["2002"],
                "month": ["6"],
                "day": ["21"],
                "hour": ["8", "10"],
            }
        )
        assert isinstance(query.time, dict)

    def test_pass_time_as_slice(self):
        query = GeoQuery(time={"start": "2000-01-01", "stop": "2001-12-21"})
        assert isinstance(query.time, slice)
        assert query.time.start == "2000-01-01"
        assert query.time.stop == "2001-12-21"

    def test_dump_original_from_time_as_combo(self):
        query = GeoQuery(
            time={
                "year": ["2002"],
                "month": ["6"],
                "day": ["21"],
                "hour": ["8", "10"],
            }
        )
        res = query.model_dump_original()
        assert isinstance(res["time"], dict)

    def test_dump_original_from_time_as_slice(self):
        query = GeoQuery(time={"start": "2000-01-01", "stop": "2001-12-21"})
        res = query.model_dump_original()
        assert isinstance(res["time"], dict)
