import os
from unittest import mock

import pytest
from intake.source.utils import reverse_format

import intake_geokube.sentinel.driver as drv
from intake_geokube.queries.geoquery import GeoQuery

from . import fixture as fxt


class TestSentinelDriver:
    @pytest.mark.parametrize(
        "item,res",
        [
            ("aaa", 1),
            (["aa", "bb"], 2),
            (10, 1),
            ([10, 100], 2),
            (("a", "b"), 2),
            ((-1, -5), 2),
        ],
    )
    def test_get_items_nbr(self, item, res):
        assert drv._get_items_nbr({"key": item}, "key") == res

    @pytest.mark.skip(reason="product_id is not mandatory anymore")
    def test_validate_query_fail_on_missing_product_id(self):
        query = GeoQuery()
        with pytest.raises(
            ValueError, match=r"\'product_id\' is mandatory filter"
        ):
            drv._validate_geoquery_for_sentinel(query)

    @pytest.mark.parametrize(
        "time",
        [
            {"year": [2000, 2014], "month": 10, "day": 14},
            {"year": 2014, "month": [10, 11], "day": 14},
            {"year": 2000, "month": 10, "day": [14, 15, 16]},
        ],
    )
    def test_validate_query_fail_on_multiple_year_month_day(self, time):
        query = GeoQuery(product_id="aaa", time=time)
        with pytest.raises(
            ValueError,
            match=(
                r"valid time combo for sentinel data should contain exactly"
                r" one*"
            ),
        ):
            drv._validate_geoquery_for_sentinel(query)

    @pytest.mark.parametrize(
        "time",
        [
            {"year": 1999, "month": 10, "day": 14},
            {"year": 2014, "month": 10, "day": 14},
            {"year": 2000, "month": 10, "day": 14},
        ],
    )
    def test_validate_query_if_time_passed_as_int(self, time):
        query = GeoQuery(product_id="aaa", time=time)
        drv._validate_geoquery_for_sentinel(query)

    @pytest.mark.parametrize(
        "time",
        [
            {"year": "1999", "month": "10", "day": "14"},
            {"year": 2014, "month": "10", "day": 14},
            {"year": "2000", "month": 10, "day": 14},
        ],
    )
    def test_validate_query_if_time_passed_as_str(self, time):
        query = GeoQuery(product_id="aaa", time=time)
        drv._validate_geoquery_for_sentinel(query)

    @pytest.mark.parametrize(
        "locs",
        [{"latitude": 10}, {"longitude": -10}, {"latitude": 5, "aaa": 10}],
    )
    def test_validate_query_Fail_on_missing_key(self, locs):
        query = GeoQuery(product_id="aa", location=locs)
        with pytest.raises(
            ValueError,
            match=(
                r"both \'latitude\' and \'longitude\' must be defined for"
                r" locatio"
            ),
        ):
            drv._validate_geoquery_for_sentinel(query)

    @pytest.mark.parametrize(
        "locs",
        [
            {"latitude": [10, -5], "longitude": [-1, -2]},
            {"latitude": 10, "longitude": [-1, -2]},
            {"latitude": [10, -5], "longitude": -1},
        ],
    )
    def test_location_to_valid_point_fail_on_multielement_list_passed(
        self, locs
    ):
        query = GeoQuery(product_id="aa", location=locs)
        with pytest.raises(
            ValueError,
            match=r"location can have just a single point \(single value for*",
        ):
            drv._location_to_valid_point(query.location)

    @pytest.mark.parametrize(
        "path,res",
        [
            (
                "/tmp/pymp-2b5gr07m/162f8f7e-c954-4f69-bb53-ed820aa6432a/S2A_MSIL2A_20231007T100031_N0509_R122_T32TQM_20231007T142901.SAFE/GRANULE/L2A_T32TQM_A043305_20231007T100026/IMG_DATA/R20m/T32TQM_20231007T100031_B01_20m.jp2",
                {
                    "product_id": "162f8f7e-c954-4f69-bb53-ed820aa6432a",
                    "resolution": "R20m",
                    "band": "B01",
                },
            ),
            (
                "/tmp/pymp-2b5gr07m/162f8f7e-c954-4f69-bb53-ed820aa6432a/S2A_MSIL2A_20231007T100031_N0509_R122_T32TQM_20231007T142901.SAFE/GRANULE/L2A_T32TQM_A043305_20231007T100026/IMG_DATA/R30m/T32TQM_20231007T100031_B04_30m.jp2",
                {
                    "product_id": "162f8f7e-c954-4f69-bb53-ed820aa6432a",
                    "resolution": "R30m",
                    "band": "B04",
                },
            ),
        ],
    )
    def test_zippatern(self, path, res):
        zippattern = "/{product_id}/{}.SAFE/GRANULE/{}/IMG_DATA/{resolution}/{}_{}_{band}_{}.jp2"
        target_dir = "/tmp/pymp-2b5gr07m"
        assert reverse_format(zippattern, path.removeprefix(target_dir)) == res

    @pytest.mark.parametrize(
        "path,exp",
        [
            (
                "/tmp/pymp-2b5gr07m/162f8f7e-c954-4f69-bb53-ed820aa6432a/S2A_MSIL2A_20231007T100031_N0509_R122_T32TQM_20231007T142901.SAFE/GRANULE/L2A_T32TQM_A043305_20231007T100026/IMG_DATA/R20m/T32TQM_20231007T100031_B01_20m.jp2",
                "R20m_B01",
            ),
            (
                "/tmp/pymp-2b5gr07m/162f8f7e-c954-4f69-bb53-ed820aa6432a/S2A_MSIL2A_20231007T100031_N0509_R122_T32TQM_20231007T142901.SAFE/GRANULE/L2A_T32TQM_A043305_20231007T100026/IMG_DATA/R30m/T32TQM_20231007T100031_B04_30m.jp2",
                "R30m_B04",
            ),
        ],
    )
    def test_get_field_name_from_path(self, path, exp):
        assert drv._get_field_name_from_path(path) == exp

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_fail_if_no_username_passed(self):
        with pytest.raises(
            KeyError,
            match=(
                r"missing at least of of the mandatory environmental"
                r" variables:"
            ),
        ):
            drv.SentinelDriver({}, "", "", "")

    def test_raise_notimplemented_for_read(self):
        with pytest.raises(
            NotImplementedError,
            match=r"reading metadata is not supported for sentinel data*",
        ):
            drv.SentinelDriver({}, "", "", "").read()

    def test_raise_notimplemented_for_load(self):
        with pytest.raises(
            NotImplementedError,
            match=r"loading entire product is not supported for sentinel data",
        ):
            drv.SentinelDriver({}, "", "", "").load()
