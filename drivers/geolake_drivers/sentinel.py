"""Geokube driver for sentinel data."""

from collections import defaultdict
from multiprocessing.util import get_temp_dir
import os
import dask
import zipfile
import glob
from functools import partial
from typing import Generator, Iterable, Mapping, Optional, List

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer
from pyproj.crs import CRS, GeographicCRS
from intake.source.utils import reverse_format

from geokube import open_datacube
from geokube.core.dataset import Dataset

from .base import GeokubeSource
from .geoquery import GeoQuery

SENSING_TIME_ATTR: str = "sensing_time"
FILE: str = "files"
DATACUBE: str = "datacube"


def get_field_name_from_path(path: str):
    res, file = path.split(os.sep)[-2:]
    band = file.split("_")[-2]
    return f"{res}_{band}"


def preprocess_sentinel(dset: xr.Dataset, pattern: str, **kw) -> xr.Dataset:
    crs = CRS.from_cf(dset["spatial_ref"].attrs)
    transformer = Transformer.from_crs(
        crs_from=crs, crs_to=GeographicCRS(), always_xy=True
    )
    x_vals, y_vals = dset["x"].to_numpy(), dset["y"].to_numpy()
    lon_vals, lat_vals = transformer.transform(*np.meshgrid(x_vals, y_vals))
    source_path = dset.encoding["source"]
    sensing_time = os.path.splitext(source_path.split(os.sep)[-6])[0].split(
        "_"
    )[-1]
    time = pd.to_datetime([sensing_time]).to_numpy()
    dset = dset.assign_coords(
        {
            "time": time,
            "latitude": (("x", "y"), lat_vals),
            "longitude": (("x", "y"), lon_vals),
        }
    ).rename({"band_data": get_field_name_from_path(source_path)})
    return dset


def get_zip_files_from_path(path: str) -> Generator:
    assert path and isinstance(path, str), "`path` must be a string"
    assert path.lower().endswith("zip"), "`path` must point to a ZIP archive"
    if "*" in path:
        yield from glob.iglob(path)
        return
    yield path


def unzip_data(files: Iterable[str], target: str) -> List[str]:
    """Unzip ZIP archive to the `target` directory."""
    target_files = []
    for file in files:
        prod_id = os.path.splitext(os.path.basename(file))[0]
        target_prod = os.path.join(target, prod_id)
        os.makedirs(target_prod, exist_ok=True)
        with zipfile.ZipFile(file) as archive:
            archive.extractall(path=target_prod)
        target_files.append(os.listdir(target_prod))
    return target_files


def _prepare_df_from_files(files: Iterable[str], pattern: str) -> pd.DataFrame:
    data = []
    for f in files:
        attr = reverse_format(pattern, f)
        attr[FILE] = f
        data.append(attr)
    return pd.DataFrame(data)


class SentinelSource(GeokubeSource):
    name = "sentinel"
    version = "0.1.0"

    def __init__(
        self,
        path: str,
        pattern: str = None,
        zippath: str = None,
        zippattern: str = None,
        metadata=None,
        xarray_kwargs: dict = None,
        mapping: Optional[Mapping[str, Mapping[str, str]]] = None,
        **kwargs,
    ):
        super().__init__(metadata=metadata, **kwargs)
        self._kube = None
        self.path = path
        self.pattern = pattern
        self.zippath = zippath
        self.zippattern = zippattern
        self.mapping = mapping
        self.metadata_caching = False
        self.xarray_kwargs = {} if xarray_kwargs is None else xarray_kwargs
        self._unzip_dir = get_temp_dir()
        self._zipdf = None
        self._jp2df = None
        assert (
            SENSING_TIME_ATTR in self.pattern
        ), f"{SENSING_TIME_ATTR} is missing in the pattern"
        self.preprocess = partial(
            preprocess_sentinel,
            pattern=self.pattern,
        )
        if self.geoquery:
            self.filters = self.geoquery.filters
        else:
            self.filters = {}

    def __post_init__(self) -> None:
        assert (
            SENSING_TIME_ATTR in self.pattern
        ), f"{SENSING_TIME_ATTR} is missing in the pattern"
        self.preprocess = partial(
            preprocess_sentinel,
            pattern=self.pattern,
        )

    def _compute_res_df(self) -> List[str]:
        self._zipdf = self._get_files_attr()
        self._maybe_select_by_zip_attrs()
        _ = unzip_data(self._zipdf[FILE].values, target=self._unzip_dir)
        self._create_jp2_df()
        self._maybe_select_by_jp2_attrs()

    def _get_files_attr(self) -> pd.DataFrame:
        df = _prepare_df_from_files(
            get_zip_files_from_path(self.path), self.pattern
        )
        assert (
            SENSING_TIME_ATTR in df
        ), f"{SENSING_TIME_ATTR} column is missing"
        return df.set_index(SENSING_TIME_ATTR).sort_index()

    def _maybe_select_by_zip_attrs(self) -> Optional[pd.DataFrame]:
        filters_to_pop = []
        for flt in self.filters:
            if flt in self._zipdf.columns:
                self._zipdf = self._zipdf.set_index(flt)
            if flt == self._zipdf.index.name:
                self._zipdf = self._zipdf.loc[self.filters[flt]]    
                filters_to_pop.append(flt)
        for f in filters_to_pop:
            self.filters.pop(f)  
        self._zipdf = self._zipdf.reset_index()                          


    def _create_jp2_df(self) -> None:
        self._jp2df = _prepare_df_from_files(
            glob.iglob(os.path.join(self._unzip_dir, self.zippath)),
            os.path.join(self._unzip_dir, self.zippattern),
        )

    def _maybe_select_by_jp2_attrs(self):
        filters_to_pop = []
        for key, value in self.filters.items():
            if key not in self._jp2df:
                continue
            if isinstance(value, str):
                self._jp2df = self._jp2df[self._jp2df[key] == value]
            elif isinstance(value, Iterable):
                self._jp2df = self._jp2df[self._jp2df[key].isin(value)]
            else:
                raise TypeError(f"type `{type(value)}` is not supported!")
            filters_to_pop.append(key)
        for f in filters_to_pop:
            self.filters.pop(f)

    def _open_dataset(self):
        self._compute_res_df()
        self._jp2df
        cubes = []
        for i, row in self._jp2df.iterrows():
            cubes.append(
                dask.delayed(open_datacube)(
                    path=row[FILE],
                    id_pattern=None,
                    mapping=self.mapping,
                    metadata_caching=self.metadata_caching,
                    **self.xarray_kwargs,
                    preprocess=self.preprocess,
                )                
            )
        self._jp2df[DATACUBE] = cubes
        self._kube = Dataset(self._jp2df.reset_index(drop=True))
        self.geoquery.filters = self.filters
        return self._kube
