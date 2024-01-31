"""Module with OData API classes definitions."""

from __future__ import annotations

__all__ = (
    "datetime_to_isoformat",
    "HttpMethod",
    "ODataRequestBuilder",
    "ODataRequest",
)

import math
import os
import warnings
from collections import defaultdict
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable

import pandas as pd
import requests
from tqdm import tqdm

from ..utils import create_zip_from_response
from .auth import SentinelAuth


def datetime_to_isoformat(date: str | datetime) -> str:
    """Convert string of datetime object to ISO datetime string.
    
    Parameters
    ----------
    data : `str` or `datetime`
    
    Returns
    -------
    date_str : str
        A ISO-compliant datetime format
    """
    if isinstance(date, str):
        try:
            value = pd.to_datetime([date]).item().isoformat()
        except ValueError as exc:
            raise ValueError(f"cannot parse '{date}' to datetime") from exc
    elif isinstance(date, datetime):
        value = value.isoformat()
    else:
        raise TypeError(f"type '{type(date)}' is not supported")
    return f"{value}Z"


class HttpMethod(Enum):
    """Enum with HTTP methods."""

    GET = auto()
    POST = auto()

    @property
    def method_name(self) -> str:
        """Get name of the HTTP method."""
        return self.name.lower()


class _ODataEntity:  # pylint: disable=too-few-public-methods
    def __init__(
        self,
        url: str,
        params: dict | None = None,
        method: HttpMethod = HttpMethod.GET,
        body: dict | None = None,
    ) -> None:
        if not params:
            self.params: dict[str, list] = defaultdict(list)
            self.conj: list = []
        if not body:
            self.body: dict = {}
        self.url = url
        self.method = method
        self.callbacks: dict = {}


class _ODataBuildableMixin:  # pylint: disable=too-few-public-methods
    odata: _ODataEntity

    def build(self) -> ODataRequest:
        """Build ODataRequest object."""
        return ODataRequest(self.odata)


class _ODataOrderMixing:  # pylint: disable=too-few-public-methods
    odata: _ODataEntity

    def order(self, by: str, desc: bool = False) -> _ODataOperation:
        """Add ordering option.

        Parameters
        ----------
        by : str
            A key by which ordering should be done
        desc : bool
            If descending order should be used
        """
        order = "desc" if desc else "asc"
        if "orderby" in self.odata.params:
            raise ValueError(
                f"ordering was already defined: {self.odata.params['orderby']}"
            )
        self.odata.params["orderby"] = [f"{by} {order}"]
        match self:
            case _ODataOperation():
                return _ODataOperation(self.odata)
            case _:
                raise TypeError(f"unexpected type: {type(self)}")


class ODataRequest:
    """OData request object."""

    _ALL_HTTP_CODES: int = -1
    _DOWNLOAD_PATTERN: str = (
        "https://zipper.dataspace.copernicus.eu"
        "/odata/v1/Products({pid})/$value"
    )

    def __init__(self, odata: _ODataEntity) -> None:
        self.request_params: dict = {}
        self.odata = odata
        self._convert_filter_param()
        self._convert_order_param()

    def _convert_order_param(self) -> None:
        if self.odata.params["orderby"]:
            self.request_params["orderby"] = self.odata.params["orderby"]

    def _convert_filter_param(self) -> None:
        param: str = ""
        for i in range(len(self.odata.params["filter"])):
            if not param:
                param = self.odata.params["filter"][i]
            else:
                param = f"{param} {self.odata.params['filter'][i]}"
            if i < len(self.odata.params["filter"]) - 1:
                param = f"{param} {self.odata.conj[i]}"
        self.request_params["filter"] = param

    def _query(
        self,
        headers: dict | None = None,
        auth: Any | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        if self.odata.params and not self.odata.url.endswith("?"):
            self.odata.url = f"{self.odata.url}?"
        params = {}
        if self.request_params:
            params = {
                f"${key}": value for key, value in self.request_params.items()
            }
        match self.odata.method:
            case HttpMethod.GET:
                return requests.get(
                    self.odata.url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
            case HttpMethod.POST:
                return requests.post(
                    self.odata.url,
                    data=self.odata.body,
                    auth=auth,
                    timeout=timeout,
                )
            case _:
                raise NotImplementedError(
                    f"method {self.odata.method} is not supported"
                )

    def with_callback(
        self,
        callback: Callable[[requests.Response], Any],
        http_code: int | None = None,
    ) -> "ODataRequest":
        """
        Add callbacks for request response.

        Parameters
        ----------
        callback : callable
            A callback function taking just a single argument,
            i.e `requests.Response` object
        http_code : int
            HTTP code for which callback should be used.
            If not passed, callback will be executed for all codes.
        """
        if http_code:
            if http_code in self.odata.callbacks:
                warnings.warn(
                    f"callback for HTTP code {http_code} will be overwritten"
                )
            self.odata.callbacks[http_code] = callback
        else:
            self.odata.callbacks[self._ALL_HTTP_CODES] = callback
        return self

    def query(
        self,
        headers: dict | None = None,
        auth: Any | None = None,
        timeout: int | None = None,
    ) -> Any:
        """Query data based on the built request.

        Parameters
        ----------
        headers : dict, optional
            Headers passed to HTTP request
        auth : Any, optional
            Authorization object or tuple (<username>,<pass>) for basic authentication

        Returns
        -------
        res : Any
            Value returned from the appropriate callback or `requests.Response` object otherwise
        """
        response = self._query(headers=headers, auth=auth, timeout=timeout)
        if response.status_code in self.odata.callbacks:
            return self.odata.callbacks[response.status_code](response)
        if self._ALL_HTTP_CODES in self.odata.callbacks:
            return self.odata.callbacks[self._ALL_HTTP_CODES](response)
        return response

    def download(
        self,
        target_dir: str,
        headers: dict | None = None,
        auth: Any | None = None,
        timeout: int | None = None,
    ) -> Any:
        """Download requested data to `target_dir`.

        Parameters
        ----------
        target_dir : str
            Path to the directory where files should be downloaded
        headers : dict, optional
            Headers passed to HTTP request
        auth : Any, optional
            Authorization object or tuple (<username>,<pass>) for basic
            authentication
        """
        os.makedirs(target_dir, exist_ok=True)
        response = self._query(headers=headers, auth=auth, timeout=timeout)
        response.raise_for_status()
        if response.status_code in self.odata.callbacks:
            self.odata.callbacks[response.status_code](response)
        if self._ALL_HTTP_CODES in self.odata.callbacks:
            self.odata.callbacks[self._ALL_HTTP_CODES](response)
        df = pd.DataFrame(response.json()["value"])
        if len(df) == 0:
            raise ValueError("no product found for the request")
        if not isinstance(auth, SentinelAuth):
            raise TypeError(
                f"expected authentication of the type '{SentinelAuth}' but"
                f" passed '{type(auth)}'"
            )
        for pid in tqdm(df["Id"]):
            response = requests.get(
                self._DOWNLOAD_PATTERN.format(pid=pid),
                stream=True,
                auth=auth,
                timeout=timeout,
            )
            response.raise_for_status()
            create_zip_from_response(
                response, os.path.join(target_dir, f"{pid}.zip")
            )


class _ODataOperation(_ODataBuildableMixin, _ODataOrderMixing):
    def __init__(self, odata: _ODataEntity) -> None:
        self.odata = odata

    def _append_query_param(self, param: str | None) -> None:
        if not param:
            return
        self.odata.params["filter"].append(param)
        self.odata.conj.append("and")

    def _validate_args(self, lt, le, eq, ge, gt) -> None:
        if eq:
            if any(map(lambda x: x is not None, [lt, le, ge, gt])):
                raise ValueError(
                    "cannot define extra operations for a single option if"
                    " `eq` is defined"
                )
        if lt and le:
            raise ValueError(
                "cannot define both operations `lt` and `le` for a single"
                " option"
            )
        if gt and ge:
            raise ValueError(
                "cannot define both operations `gt` and `ge` for a single"
                " option"
            )

    def and_(self) -> _ODataOperation:
        """Put conjunctive conditions."""
        self.odata.conj[-1] = "and"
        return self

    def or_(self) -> _ODataOperation:
        """Put alternative conditions."""
        self.odata.conj[-1] = "or"
        return self

    def filter_attr(self, name: str, value: str) -> _ODataOperation:
        """Filter by attribute value.

        Parameters
        ----------
        name : str
            Name of an attribute
        value : str
            Value of the attribute
        """
        param: str = (
            "Attributes/OData.CSC.ValueTypeAttribute/any(att:att/Name eq"
            f" ‘[{name}]’"
            + f"and att/OData.CSC.ValueTypeAttribute/Value eq ‘{value}]’)"
        )
        self._append_query_param(param)
        return self

    def filter(
        self,
        name: str,
        *,
        lt: str | None = None,
        le: str | None = None,
        eq: str | None = None,
        ge: str | None = None,
        gt: str | None = None,
        containing: str | None = None,
        not_containing: str | None = None,
    ) -> _ODataOperation:
        """Filter option by values.

        Add filter option to the request. Value of an option indicated by
        the `name` argument will be checked agains given values or arguments.
        You cannot specify both `lt` and `le` or `ge` and `gt.

        Parameters
        ----------
        lt : str, optional
            value for `less than` comparison
        le : str, optional
            value for `less ord equal` comparison
        eq : str, optional
            value for `equal` comparison
        ge : str, optional
            value for `greater or equal` comparison
        gt : str, optional
            value for `greater than` comparison
        containing : str, optional
            value to be contained
        not_containing : str, optional
            value not to be containing
        """
        if not any([le, lt, eq, ge, gt, containing, not_containing]):
            return self
        self._validate_args(le=le, lt=lt, eq=eq, ge=ge, gt=gt)
        build_: _ODataOperation = self
        assert isinstance(build_, _ODataOperation), "unexpected type"
        if lt:
            build_ = build_.with_option_lt(name, lt).and_()
        if le:
            build_ = build_.with_option_le(name, le).and_()
        if eq:
            build_ = build_.with_option_equal(name, eq).and_()
        if ge:
            build_ = build_.with_option_ge(name, ge).and_()
        if gt:
            build_ = build_.with_option_gt(name, gt).and_()
        if containing:
            build_ = build_.with_option_containing(name, containing).and_()
        if not_containing:
            build_ = build_.with_option_not_containing(
                name, not_containing
            ).and_()

        return build_

    def filter_date(
        self,
        name: str,
        *,
        lt: str | None = None,
        le: str | None = None,
        eq: str | None = None,
        ge: str | None = None,
        gt: str | None = None,
    ) -> _ODataOperation:
        """
        Filter datetetime option by values.

        Add filter option to the request. Datetime values of an option
        indicated by the `name` argument will be checked agains given
        values or arguments.
        Values of arguments will be automatically  converted to ISO datetime
        string format.
        You cannot specify both `lt` and `le` or `ge` and `gt.

        Parameters
        ----------
        lt : str, optional
            value for `less than` comparison
        le : str, optional
            value for `less ord equal` comparison
        eq : str, optional
            value for `equal` comparison
        ge : str, optional
            value for `greater or equal` comparison
        gt : str, optional
            value for `greater than` comparison
        """
        if lt:
            lt = datetime_to_isoformat(lt)
        if le:
            le = datetime_to_isoformat(le)
        if eq:
            eq = datetime_to_isoformat(eq)
        if ge:
            ge = datetime_to_isoformat(ge)
        if gt:
            gt = datetime_to_isoformat(gt)
        return self.filter(name, lt=lt, le=le, eq=eq, ge=ge, gt=gt)

    def with_option_equal(self, name: str, value: str) -> "_ODataOperation":
        """Add filtering by option `is equal`."""
        param: str = f"{name} eq '{value}'"
        self._append_query_param(param)
        return self

    def with_option_containing(
        self, name: str, value: str
    ) -> "_ODataOperation":
        """Add filtering by option `containing`."""
        param: str = f"contains({name},'{value}')"
        self._append_query_param(param)
        return self

    def with_option_not_containing(
        self, name: str, value: str
    ) -> "_ODataOperation":
        """Add filtering by option `not containing`."""
        param: str = f"not contains({name},'{value}')"
        self._append_query_param(param)
        return self

    def with_option_equal_list(
        self, name: str, value: list[str]
    ) -> "_ODataOperation":
        """Add filtering by equality."""
        self.odata.body.update({"FilterProducts": [{name: v} for v in value]})
        self.odata.method = HttpMethod.POST
        return self

    def with_option_lt(self, name: str, value: str) -> "_ODataOperation":
        """Add filtering with `less than` option."""
        param: str = f"{name} lt {value}"
        self._append_query_param(param)
        return self

    def with_option_le(self, name: str, value: str) -> "_ODataOperation":
        """Add filtering with `less or equal` option."""
        param: str = f"{name} le {value}"
        self._append_query_param(param)
        return self

    def with_option_gt(self, name: str, value: str) -> "_ODataOperation":
        """Add filtering with `greater or equal` option."""
        param: str = f"{name} gt {value}"
        self._append_query_param(param)
        return self

    def with_option_ge(self, name: str, value: str) -> "_ODataOperation":
        """Add filtering with `greater than` option."""
        param: str = f"{name} ge {value}"
        self._append_query_param(param)
        return self

    def intersect_polygon(
        self,
        polygon: list[tuple[float, float]] | list[list[float]],
        srid: str | None = "4326",
    ) -> "_ODataOperation":
        """
        Add filtering by polygon intersection.

        Parameters
        ----------
        polygon: list of 2-element tuple or 2-element lists of floats
            Points belonging to the polygon [longitude, latitude].
            The 1st at the last point needs to be the same (polygon needs
            to be closed)
        srid : str, optional
            SRID name, currently supported is only `4326`
        """
        if srid != "4326":
            raise NotImplementedError(
                "currently supported SRID is only ['4326' (EPSG 4326)]"
            )
        if not polygon:
            return self
        if any(map(lambda x: len(x) != 2, polygon)):
            raise ValueError(
                "polygon should be defined as a 2-element list or tuple"
                " (containing latitude and longitude values)"
            )
        if not math.isclose(polygon[0][0], polygon[-1][0]) or not math.isclose(
            polygon[0][1], polygon[-1][1]
        ):
            raise ValueError(
                "polygon needs to end at the same point it starts!"
            )
        polygon_repr = ",".join([f"{p[1]} {p[0]}" for p in polygon])
        param = f"OData.CSC.Intersects(area=geography'SRID={srid};POLYGON(({polygon_repr}))')"
        self._append_query_param(param)
        return self

    def intersect_point(
        self,
        point: list[float] | tuple[float, float],
        srid: str | None = "4326",
    ) -> "_ODataOperation":
        """Add filtering by intersection with a point.

        Parameters
        ----------
        point: 2-element tuple or list of floats
            Point definition [latitude, longitude]
        srid : str, optional
            SRID name, currently supported is only `4326`
        """
        if srid != "4326":
            raise NotImplementedError(
                "currently supported SRID is only ['4326' (EPSG 4326)]"
            )
        if len(point) > 2:
            # NOTE: to assure the order is [latitude, longitude] and not vice versa!
            raise ValueError(
                "point need to have just two elemens [latitude, longitude]"
            )
        param = (
            f"OData.CSC.Intersects(area=geography'SRID={srid};POINT({point[0]} {point[1]})')"
        )
        self._append_query_param(param)
        return self


class ODataRequestBuilder(
    _ODataOperation
):  # pylint: disable=too-few-public-methods
    """OData API request builder."""

    _BASE_PATTERN: str = "{url}/Products"

    @classmethod
    def new(cls, url: str) -> _ODataOperation:
        """Start building OData request."""
        url = cls._BASE_PATTERN.format(url=url.strip("/"))
        return _ODataOperation(_ODataEntity(url=url))
