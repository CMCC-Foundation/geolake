"""Geokube driver for sentinel data."""

import glob
import os
import string
import zipfile
from multiprocessing.util import get_temp_dir
from typing import Collection, NoReturn

import dask
import numpy as np
import pandas as pd
import xarray as xr
from geokube.backend.netcdf import open_datacube
from geokube.core.dataset import Dataset
from intake.source.utils import reverse_format
from pyproj import Transformer
from pyproj.crs import CRS, GeographicCRS

from ..base import AbstractBaseDriver
from ..queries.geoquery import GeoQuery
from ..queries.types import BoundingBoxDict, TimeComboDict
from .auth import SentinelAuth
from .odata_builder import ODataRequest, ODataRequestBuilder


def _get_items_nbr(mapping, key) -> int:
    if isinstance(mapping[key], str):
        return 1
    return len(mapping[key]) if isinstance(mapping[key], Collection) else 1


def _validate_geoquery_for_sentinel(query: GeoQuery) -> None:
    if query.time:
        if isinstance(query.time, dict) and any([
            _get_items_nbr(query.time, "year") != 1,
            _get_items_nbr(query.time, "month") != 1,
            _get_items_nbr(query.time, "day") != 1,
        ]):
            raise ValueError(
                "valid time combo for sentinel data should contain exactly one"
                " value for 'year', one for 'month', and one for 'day'"
            )
    if query.location and (
        "latitude" not in query.location or "longitude" not in query.location
    ):
        raise ValueError(
            "both 'latitude' and 'longitude' must be defined for location"
        )


def _bounding_box_to_polygon(
    bbox: BoundingBoxDict,
) -> list[tuple[float, float]]:
    return [
        (bbox["north"], bbox["west"]),
        (bbox["north"], bbox["east"]),
        (bbox["south"], bbox["east"]),
        (bbox["south"], bbox["west"]),
        (bbox["north"], bbox["west"]),
    ]


def _timecombo_to_day_range(combo: TimeComboDict) -> tuple[str, str]:
    return (f"{combo['year']}-{combo['month']}-{combo['day']}T00:00:00",
            f"{combo['year']}-{combo['month']}-{combo['day']}T23:59:59")


def _location_to_valid_point(
    location: dict[str, float | list[float]]
) -> tuple[float, float]:
    if isinstance(location["latitude"], list):
        if len(location["latitude"]) > 1:
            raise ValueError(
                "location can have just a single point (single value for"
                " 'latitude' and 'longitude')"
            )
        lat = location["latitude"][0]
    else:
        lat = location["latitude"]
    if isinstance(location["longitude"], list):
        if len(location["longitude"]) > 1:
            raise ValueError(
                "location can have just a single point (single value for"
                " 'latitude' and 'longitude')"
            )
        lon = location["longitude"][0]
    else:
        lon = location["longitude"]
    return (lat, lon)


def _validate_path_and_pattern(path: str, pattern: str):
    if path.startswith(os.sep) or pattern.startswith(os.sep):
        raise ValueError(f"path and pattern cannot start with {os.sep}")


def _get_attrs_keys_from_pattern(pattern: str) -> list[str]:
    return list(
        map(
            lambda x: str(x[1]),
            filter(lambda x: x[1], string.Formatter().parse(pattern)),
        )
    )


def unzip_and_clear(target: str) -> None:
    """Unzip ZIP archives in 'target' dir and remove archive."""
    assert os.path.exists(target), f"directory '{target}' does not exist"
    for file in os.listdir(target):
        if not file.endswith(".zip"):
            continue
        prod_id = os.path.splitext(os.path.basename(file))[0]
        target_prod = os.path.join(target, prod_id)
        os.makedirs(target_prod, exist_ok=True)
        try:
            with zipfile.ZipFile(os.path.join(target, file)) as archive:
                archive.extractall(path=target_prod)
        except zipfile.BadZipFile as err:
            raise RuntimeError("downloaded ZIP archive is invalid") from err
        os.remove(os.path.join(target, file))


def _get_field_name_from_path(path: str):
    res, file = path.split(os.sep)[-2:]
    band = file.split("_")[-2]
    return f"{res}_{band}"


def preprocess_sentinel(dset: xr.Dataset) -> xr.Dataset:
    """Preprocessing function for sentinel data.

    Parameters
    ----------
    dset :  xarray.Dataset
        xarray.Dataset to be preprocessed

    Returns
    -------
    ds : xarray.Dataset
        Preprocessed xarray.Dataset
    """
    crs = CRS.from_cf(dset["spatial_ref"].attrs)
    transformer = Transformer.from_crs(
        crs_from=crs, crs_to=GeographicCRS(), always_xy=True
    )
    x_vals, y_vals = dset["x"].to_numpy(), dset["y"].to_numpy()
    lon_vals, lat_vals = transformer.transform(*np.meshgrid(x_vals, y_vals))  # type: ignore[call-overload] # pylint: disable=unpacking-non-sequence
    source_path = dset.encoding["source"]
    sensing_time = os.path.splitext(source_path.split(os.sep)[-6])[0].split(
        "_"
    )[-1]
    time = pd.to_datetime([sensing_time]).to_numpy()
    dset = dset.assign_coords({
        "time": time,
        "latitude": (("x", "y"), lat_vals),
        "longitude": (("x", "y"), lon_vals),
    }).rename({"band_data": _get_field_name_from_path(source_path)})
    expanded_timedim_dataarrays = {var_name: dset[var_name].expand_dims('time') for var_name in dset.data_vars}
    dset = dset.update(expanded_timedim_dataarrays)
    return dset


class _SentinelKeys:  # pylint: disable=too-few-public-methods
    UUID: str = "Id"
    SENSING_TIME: str = "ContentDate/Start"
    TYPE: str = "Name"


class SentinelDriver(AbstractBaseDriver):
    """Driver class for sentinel data."""

    name: str = "sentinel_driver"
    version: str = "0.1b0"

    def __init__(
        self,
        metadata: dict,
        url: str,
        zippattern: str,
        zippath: str,
        type: str,
        username: str | None = None,
        password: str | None = None,
        sentinel_timeout: int | None = None,
        mapping: dict | None = None,
        xarray_kwargs: dict | None = None,
    ) -> None:
        super().__init__(metadata=metadata)
        self.url: str = url
        self.zippattern: str = zippattern
        self.zippath: str = zippath
        self.type_ = type
        _validate_path_and_pattern(path=self.zippath, pattern=self.zippattern)
        self.auth: SentinelAuth = self._get_credentials(username, password)
        self.target_dir: str = get_temp_dir()
        self.sentinel_timeout: int | None = sentinel_timeout
        self.mapping: dict = mapping or {}
        self.xarray_kwargs: dict = xarray_kwargs or {}

    def _get_credentials(
        self, username: str | None, password: str | None
    ) -> SentinelAuth:
        if username and password:
            return SentinelAuth(
                username=username,
                password=password,
            )
        self.log.debug("getting credentials from environmental variables...")
        if (
            "SENTINEL_USERNAME" not in os.environ
            or "SENTINEL_PASSWORD" not in os.environ
        ):
            self.log.error(
                "missing at least of of the mandatory environmental variables:"
                " ['SENTINEL_USERNAME', 'SENTINEL_PASSWORD']"
            )
            raise KeyError(
                "missing at least of of the mandatory environmental variables:"
                " ['SENTINEL_USERNAME', 'SENTINEL_PASSWORD']"
            )
        return SentinelAuth(
            username=os.environ["SENTINEL_USERNAME"],
            password=os.environ["SENTINEL_PASSWORD"],
        )

    def _force_sentinel_type(self, builder):
        self.log.info("forcing sentinel type: %s...", self.type_)
        return builder.filter(_SentinelKeys.TYPE, containing=self.type_)

    def _filter_by_sentinel_attrs(self, builder, query: GeoQuery):
        self.log.info("filtering by sentinel attributes...")
        path_filter_names: set[str] = {
            parsed[1]
            for parsed in string.Formatter().parse(self.zippattern)
            if parsed[1]
        }
        if not query.filters:
            return builder
        sentinel_filter_names: set[str] = (
            query.filters.keys() - path_filter_names
        )
        for sf in sentinel_filter_names:
            builder = builder.filter_attr(sf, query.filters[sf])
        return builder

    def _build_odata_from_geoquery(self, query: GeoQuery) -> ODataRequest:
        self.log.debug("validating geoquery...")
        _validate_geoquery_for_sentinel(query)
        self.log.debug("constructing odata request...")
        builder = ODataRequestBuilder.new(url=self.url)
        if "product_id" in query.filters:
            builder = builder.filter(
                name=_SentinelKeys.UUID, eq=query.filters.get("product_id")
            )
        builder = self._filter_by_sentinel_attrs(builder, query=query)
        builder = self._force_sentinel_type(builder)
        if query.time:
            if isinstance(query.time, dict):
                timecombo_start, timecombo_end = _timecombo_to_day_range(query.time)
                self.log.debug("filtering by timecombo: [%s, %s] ", timecombo_start, timecombo_end)
                builder = builder.filter_date(
                    _SentinelKeys.SENSING_TIME, ge=timecombo_start, le=timecombo_end
                )
            elif isinstance(query.time, slice):
                self.log.debug("filtering by slice: %s", query.time)
                builder = builder.filter_date(
                    _SentinelKeys.SENSING_TIME,
                    ge=query.time.start,
                    le=query.time.stop,
                )
        if query.area:
            self.log.debug("filering by polygon")
            polygon = _bounding_box_to_polygon(query.area)
            builder = builder.intersect_polygon(polygon=polygon)
        if query.location:
            self.log.debug("filering by location")
            point = _location_to_valid_point(query.location)
            builder = builder.intersect_point(point=point)
        return builder.build()

    def _prepare_dataset(self) -> Dataset:
        data: list = []
        attrs_keys: list[str] = _get_attrs_keys_from_pattern(self.zippattern)
        for f in glob.glob(os.path.join(self.target_dir, self.zippath)):
            self.log.debug("processsing file %s", f)
            file_no_tmp_dir = f.removeprefix(self.target_dir).strip(os.sep)
            attr = reverse_format(self.zippattern, file_no_tmp_dir)
            attr[Dataset.FILES_COL] = [f]
            data.append(attr)
        # NOTE: eventually, join files if there are several for the same attrs
        # combintation
        df = (
            pd.DataFrame(data)
            .groupby(attrs_keys)
            .agg({Dataset.FILES_COL: sum})
        )
        datacubes = []
        for ind, files in df.iterrows():
            load = dict(zip(df.index.names, ind))
            load[Dataset.FILES_COL] = files
            load[Dataset.DATACUBE_COL] = dask.delayed(open_datacube)(
                path=files.item(),
                id_pattern=None,
                mapping=self.mapping,
                metadata_caching=False,
                **self.xarray_kwargs,
                preprocess=preprocess_sentinel,
            )
            datacubes.append(load)
        return Dataset(pd.DataFrame(datacubes))

    def read(self) -> NoReturn:
        """Read sentinel data."""
        raise NotImplementedError(
            "reading metadata is not supported for sentinel data"
        )

    def load(self) -> NoReturn:
        """Load sentinel data."""
        raise NotImplementedError(
            "loading entire product is not supported for sentinel data"
        )

    def process(self, query: GeoQuery) -> Dataset:
        """Process sentinel data according to the `query`.

        Returns
        -------
        cube : `geokube.Dataset`
        
        Examples
        --------
        ```python
        >>> data = catalog['sentinel']['prod_name'].process(query)
        ```
        """
        self.log.info("builder odata request based on passed geoquery...")
        req = self._build_odata_from_geoquery(query)
        self.log.info("downloading data...")
        req.download(
            target_dir=self.target_dir,
            auth=self.auth,
            timeout=self.sentinel_timeout,
        )
        self.log.info("unzipping and removing archives...")
        unzip_and_clear(self.target_dir)
        self.log.info("preparing geokube.Dataset...")
        dataset = self._prepare_dataset()
        dataset = super()._process_geokube_dataset(
            dataset, query=query, compute=True
        )
        return dataset
