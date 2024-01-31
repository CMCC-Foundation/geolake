from multiprocessing import Value
from unittest import mock

import pytest
from requests import Response, Session

from intake_geokube.sentinel.odata_builder import (
    HttpMethod,
    ODataRequest,
    ODataRequestBuilder,
    _ODataEntity,
    _ODataOperation,
    _ODataOrderMixing,
    datetime_to_isoformat,
)


@pytest.fixture
def odata() -> _ODataEntity:
    return _ODataEntity(url="http://url.com/v1")


@pytest.fixture
def odata_op(odata) -> _ODataOperation:
    return _ODataOperation(odata=odata)


class TestHttpMethod:
    @pytest.mark.parametrize(
        "method,res", [(HttpMethod.GET, "get"), (HttpMethod.POST, "post")]
    )
    def test_get_proper_name(self, method, res):
        assert method.method_name == res


class TestODataRequestBuildable:
    def test_build_from_operation(self, odata):
        res = _ODataOperation(odata).build()
        assert isinstance(res, ODataRequest)
        assert res.odata == odata


class TestOrderMixin:
    @pytest.mark.parametrize("type_", [_ODataOperation])
    def test_proper_class_when_order(self, type_, odata):
        res = type_(odata).order(by="ProductionDate")
        assert isinstance(res, type_)

    def test_fail_order_on_wrong_superclass(self, odata):
        class A(_ODataOrderMixing):
            def __init__(self, odata):
                self.odata = odata

        with pytest.raises(TypeError, match=r"unexpected type:*"):
            A(odata).order(by="a")


class TestODataRequest:
    def test_convert_filter_param(self, odata_op):
        odata_op.filter("a", eq=10).or_().filter("b", lt=100, ge=10).order(
            by="a", desc=True
        )
        req = ODataRequest(odata_op.odata)
        assert req.odata.params["filter"] == [
            "a eq '10'",
            "b lt 100",
            "b ge 10",
        ]
        assert (
            req.request_params["filter"] == "a eq '10' or b lt 100 and b ge 10"
        )
        assert req.odata.params["orderby"] == ["a desc"]


class TestODataRequestBuilder:
    def test_create_odata_operation_from_builder(self):
        res = ODataRequestBuilder.new(url="http:/url.com")
        assert isinstance(res, _ODataOperation)
        assert res.odata.url == "http:/url.com/Products"


class TestODataOperation:
    @pytest.fixture
    def odata_request(self) -> ODataRequest:
        return ODataRequestBuilder.new("http://aaaa.com").build()

    @pytest.mark.parametrize(
        "datestring,result",
        [
            ("2002-02-01", "2002-02-01T00:00:00Z"),
            ("2001-02-02 12:45", "2001-02-02T12:45:00Z"),
            ("1977-12-23 11:00:05", "1977-12-23T11:00:05Z"),
            ("1977-12-23T11:00:05", "1977-12-23T11:00:05Z"),
        ],
    )
    def test_convert_to_isoformat(self, datestring, result):
        assert datetime_to_isoformat(datestring) == result

    def testwith_option_equal(self, odata_op):
        odata_op.with_option_equal("Name", "some_name")
        assert len(odata_op.odata.params) == 1
        assert odata_op.odata.method is HttpMethod.GET
        assert odata_op.odata.params["filter"] == ["Name eq 'some_name'"]

    def test_option_containing(self, odata_op):
        odata_op.with_option_containing("some_option", "aaa")
        assert len(odata_op.odata.params) == 1
        assert odata_op.odata.method is HttpMethod.GET
        assert odata_op.odata.params["filter"] == [
            "contains(some_option,'aaa')"
        ]

    def test_option_not_containing(self, odata_op):
        odata_op.with_option_not_containing("some_option", "aaa")
        assert len(odata_op.odata.params) == 1
        assert odata_op.odata.method is HttpMethod.GET
        assert odata_op.odata.params["filter"] == [
            "not contains(some_option,'aaa')"
        ]

    def testwith_option_equal_list(self, odata_op):
        odata_op.with_option_equal_list("Name", ["some_name", "aaa"])
        assert len(odata_op.odata.params) == 0
        assert odata_op.odata.method is HttpMethod.POST
        assert odata_op.odata.body == {
            "FilterProducts": [{"Name": "some_name"}, {"Name": "aaa"}]
        }

    def test_several_options(self, odata_op):
        odata_op.with_option_equal("aa", "bb").and_().with_option_lt(
            "aaa", "1000"
        )
        assert odata_op.odata.method is HttpMethod.GET
        assert len(odata_op.odata.params) == 1
        assert odata_op.odata.params["filter"] == ["aa eq 'bb'", "aaa lt 1000"]

    @pytest.mark.parametrize(
        "comb",
        [
            {"lt": 1, "eq": 10},
            {"le": 1, "eq": 10},
            {"lt": 1, "le": 10},
            {"gt": 1, "ge": 10},
            {"ge": 1, "eq": 10},
            {"gt": 1, "eq": 10},
            {"lt": 1, "eq": 1, "ge": 1},
        ],
    )
    def test_filter_fail_on_wrong_arguments_passed(self, comb, odata_op):
        with pytest.raises(ValueError, match=r"cannot define *"):
            odata_op.filter(name="a", **comb)

    def test_filter_single(self, odata_op):
        res = odata_op.filter(name="a", lt=100)
        assert res.odata.params["filter"] == ["a lt 100"]

    def test_filter_multiple(self, odata_op):
        res = odata_op.filter(name="a", lt=100, gt=10)
        assert res.odata.params["filter"] == ["a lt 100", "a gt 10"]
        assert res.odata.conj[-1] == "and"

    def test_filter_multiple2(self, odata_op):
        res = odata_op.filter(name="a", ge=10, le=100)
        assert res.odata.params["filter"] == ["a le 100", "a ge 10"]
        assert res.odata.conj[-1] == "and"

    def test_filter_multiple3(self, odata_op):
        res = odata_op.filter(name="a", eq=10)
        assert res.odata.params["filter"] == ["a eq '10'"]
        assert res.odata.conj[-1] == "and"

    @pytest.mark.parametrize("arr", ["111", "111", "02-20", "56:45", "aaa"])
    def test_filter_date_fail_arg_nondateparsable(self, arr, odata_op):
        with pytest.raises(ValueError, match=r"cannot parse*"):
            odata_op.filter_date("ProductionDate", lt=arr)

    @pytest.mark.parametrize("arr", [(1,), 1, 1.2, [1, 2], {1, 2}])
    def test_filter_date_fail_arg_wrong_type(self, arr, odata_op):
        with pytest.raises(TypeError, match=r"type .* is not supported"):
            odata_op.filter_date("ProductionDate", lt=arr)

    def test_filter_and_order_ascending(self, odata_op):
        odata_op.with_option_gt("aaa", "-50").order(
            by="ProductionDate", desc=False
        )
        assert odata_op.odata.method is HttpMethod.GET
        assert len(odata_op.odata.params) == 2
        assert odata_op.odata.body == {}
        assert odata_op.odata.params["filter"] == ["aaa gt -50"]
        assert odata_op.odata.params["orderby"] == ["ProductionDate asc"]

    def test_filter_and_order_descending(self, odata_op):
        odata_op.with_option_gt("aaa", "-50").order(
            by="ProductionDate", desc=True
        )
        assert odata_op.odata.method is HttpMethod.GET
        assert len(odata_op.odata.params) == 2
        assert odata_op.odata.body == {}
        assert odata_op.odata.params["filter"] == ["aaa gt -50"]
        assert odata_op.odata.params["orderby"] == ["ProductionDate desc"]

    @mock.patch.object(Session, "send")
    def test_request_data(self, send_mock, odata_op):
        send_mock.json.return_value = "{'response': 'some response'}"
        _ = (
            odata_op.with_option_gt("aaa", "-50")
            .order(by="ProductionDate", desc=True)
            .build()
            .query()
        )
        send_mock.assert_called_once()
        assert (
            send_mock.call_args_list[0].args[0].url
            == "http://url.com/v1?%24filter=aaa+gt+-50&%24orderby=ProductionDate+desc"
        )

    @mock.patch.object(Session, "send")
    def test_url_passed_with_extra_slashes(self, send_mock):
        builder = ODataRequestBuilder.new(
            "https://some_url.com/odata/v1"
        ).build()
        assert builder.odata.url == "https://some_url.com/odata/v1/Products"

    def test_polygon_fail_on_other_srid_passed(self, odata_op):
        with pytest.raises(
            NotImplementedError, match=r"currently supported SRID is only*"
        ):
            odata_op.intersect_polygon(
                polygon=[[0, 1], [1, 2], [0, 1]], srid="123"
            )

    def test_polygon_fail_on_polygon_with_more_than_two_coords(self, odata_op):
        with pytest.raises(
            ValueError,
            match=r"polygon should be defined as a 2-element list or tuple*",
        ):
            odata_op.intersect_polygon(polygon=[[0, 1], [1, 2, 3], [0, 1]])

    def test_polygon_fail_on_polygon_ending_not_on_start_point(self, odata_op):
        with pytest.raises(
            ValueError,
            match=r"polygon needs to end at the same point it starts!",
        ):
            odata_op.intersect_polygon(polygon=[[0, 1], [1, 3], [1, 1]])

    def test_location_fail_on_other_srid_passed(self, odata_op):
        with pytest.raises(
            NotImplementedError, match=r"currently supported SRID is only*"
        ):
            odata_op.intersect_point(point=(0.1, 2.0), srid="123")

    def test_location_fail_on_more_than_two_coords(self, odata_op):
        with pytest.raises(
            ValueError, match=r"point need to have just two elemens*"
        ):
            odata_op.intersect_point(point=[0, 1, 4])

    @mock.patch.object(Session, "send")
    @pytest.mark.parametrize(
        "code,callback", [(200, lambda r: "ok"), (400, lambda r: "bad")]
    )
    def test_callback_call_on_defined(
        self, send_mock, code, callback, odata_request
    ):
        response = Response()
        response.status_code = code
        send_mock.return_value = response
        res = odata_request.with_callback(callback, code).query()
        assert res == callback(None)

    @mock.patch.object(Session, "send")
    def test_return_response_on_missing_callback(
        self, send_mock, odata_request
    ):
        response = Response()
        response.status_code = 200
        send_mock.return_value = response
        res = odata_request.query()
        assert isinstance(res, Response)

    @mock.patch.object(Session, "send")
    @pytest.mark.parametrize("code", [200, 300, 305, 400, 500])
    def test_callback_without_http_code(self, send_mock, code, odata_request):
        response = Response()
        response.status_code = code
        send_mock.return_value = response
        callback = mock.MagicMock()
        _ = odata_request.with_callback(callback).query()
        callback.assert_called_with(response)

    def test_operations_with_auto_conjunction(self, odata_op):
        res = odata_op.filter("a", lt=10).filter("b", ge="aaa")
        assert res.odata.params["filter"] == ["a lt 10", "b ge aaa"]
        assert len(res.odata.conj) == 2
        assert res.odata.conj == ["and", "and"]

    def test_operations_with_auto_conjunction_with_several_operations(
        self, odata_op
    ):
        res = (
            odata_op.filter("a", lt=10)
            .filter("b", ge="aaa")
            .filter_date("ProductioNDate", lt="2000-01-01")
        )
        assert res.odata.params["filter"] == [
            "a lt 10",
            "b ge aaa",
            "ProductioNDate lt 2000-01-01T00:00:00Z",
        ]
        assert len(res.odata.conj) == 3
        assert res.odata.conj == ["and", "and", "and"]

    def test_operations_with_auto_and_explicit_conjunction_with_several_operations(
        self, odata_op
    ):
        res = (
            odata_op.filter("a", lt=10)
            .filter("b", ge="aaa")
            .or_()
            .filter_date("ProductioNDate", lt="2000-01-01")
        )
        assert res.odata.params["filter"] == [
            "a lt 10",
            "b ge aaa",
            "ProductioNDate lt 2000-01-01T00:00:00Z",
        ]
        assert len(res.odata.conj) == 3
        assert res.odata.conj == ["and", "or", "and"]

    def test_con_conj_on_single_operation(self, odata_op):
        res = odata_op.filter("a", lt=10)
        assert res.odata.params["filter"] == ["a lt 10"]
        assert len(res.odata.conj) == 1

    def test_operations_with_explicit_conjunction_and(self, odata_op):
        res = odata_op.filter("a", lt=10).and_().filter("b", ge="aaa")
        assert res.odata.params["filter"] == ["a lt 10", "b ge aaa"]
        assert len(res.odata.conj) == 2
        assert res.odata.conj == ["and", "and"]

    def test_operations_with_explicit_conjunction_or(self, odata_op):
        res = odata_op.filter("a", lt=10).or_().filter("b", ge="aaa")
        assert res.odata.params["filter"] == ["a lt 10", "b ge aaa"]
        assert len(res.odata.conj) == 2
        assert res.odata.conj == ["or", "and"]

    def test_operation_with_idempotent_same_conjunction(self, odata_op):
        res = odata_op.filter("a", lt=10).or_().or_().filter("b", ge="aaa")
        assert res.odata.params["filter"] == ["a lt 10", "b ge aaa"]
        assert len(res.odata.conj) == 2
        assert res.odata.conj == ["or", "and"]

    def test_operation_with_idempotent_other_conjunction(self, odata_op):
        res = (
            odata_op.filter("a", lt=10)
            .or_()
            .or_()
            .and_()
            .filter("b", ge="aaa")
        )
        assert res.odata.params["filter"] == ["a lt 10", "b ge aaa"]
        assert len(res.odata.conj) == 2
        assert res.odata.conj == ["and", "and"]

    def test_filter_skip_if_all_arg_nones(self, odata_op):
        odata_op = odata_op.filter("a").filter("b")
        assert len(odata_op.odata.params) == 0
        assert len(odata_op.odata.conj) == 0

    def test_filter_containing(self, odata_op):
        odata_op = odata_op.filter("a", containing="ggg", not_containing="bbb")
        assert odata_op.odata.params["filter"] == [
            "contains(a,'ggg')",
            "not contains(a,'bbb')",
        ]
        assert odata_op.odata.conj == ["and", "and"]
