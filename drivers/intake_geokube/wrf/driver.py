"""WRF driver for GeoLake."""

from functools import partial
from typing import Any

import numpy as np
import xarray as xr
from geokube import open_datacube, open_dataset
from geokube.core.datacube import DataCube
from geokube.core.dataset import Dataset

from ..base import AbstractBaseDriver

_DIM_RENAME_MAP: dict = {
    "Time": "time",
    "south_north": "latitude",
    "west_east": "longitude",
}
_COORD_RENAME_MAP: dict = {
    "XTIME": "time",
    "XLAT": "latitude",
    "XLONG": "longitude",
}
_COORD_SQUEEZE_NAMES: tuple = ("latitude", "longitude")
_PROJECTION: dict = {"grid_mapping_name": "latitude_longitude"}


def _cast_to_set(item: Any) -> set:
    if item is None:
        return set()
    if isinstance(item, set):
        return item
    if isinstance(item, str):
        return {item}
    if isinstance(item, list):
        return set(item)
    raise TypeError(f"type '{type(item)}' is not supported!")


def rename_coords(dset: xr.Dataset) -> xr.Dataset:
    """Rename coordinates."""
    dset_ = dset.rename_vars(_COORD_RENAME_MAP)
    # Removing `Time` dimension from latitude and longitude.
    coords = dset_.coords
    for name in _COORD_SQUEEZE_NAMES:
        coord = dset_[name]
        if "Time" in coord.dims:
            coords[name] = coord.squeeze(dim="Time", drop=True)
    return dset_


def change_dims(dset: xr.Dataset) -> xr.Dataset:
    """Change dimensions to time, latitude, and longitude."""
    # Preparing new horizontal coordinates.
    lat = (["south_north"], dset["latitude"].to_numpy().mean(axis=1))
    lon = (["west_east"], dset["longitude"].to_numpy().mean(axis=0))
    # Removing old horizontal coordinates.
    dset_ = dset.drop_vars(["latitude", "longitude"])
    # Adding new horizontal coordinates and setting their units.
    coords = dset_.coords
    coords["latitude"] = lat
    coords["longitude"] = lon
    dset_["latitude"].attrs["units"] = "degree_north"
    dset_["longitude"].attrs["units"] = "degree_east"
    # Making `time`, `latitude`, and `longitude` new dimensions, instead of
    # `Time`, `south_north`, and `west_east`.
    dset_ = dset_.swap_dims(_DIM_RENAME_MAP)
    return dset_


def add_projection(dset: xr.Dataset) -> xr.Dataset:
    """Add projection information to the dataset."""
    coords = dset.coords
    coords["crs"] = xr.DataArray(data=np.array(1), attrs=_PROJECTION)
    for var in dset.data_vars.values():
        enc = var.encoding
        enc["grid_mapping"] = "crs"
        if coord_names := enc.get("coordinates"):
            for old_name, new_name in _COORD_RENAME_MAP.items():
                coord_names = coord_names.replace(old_name, new_name)
            enc["coordinates"] = coord_names
    return dset


def choose_variables(
    dset: xr.Dataset,
    variables_to_keep: str | list[str] | None = None,
    variables_to_skip: str | list[str] | None = None,
) -> xr.Dataset:
    """Choose only some variables by keeping or skipping some of them."""
    variables_to_keep_ = _cast_to_set(variables_to_keep)
    variables_to_skip_ = _cast_to_set(variables_to_skip)
    selected_variables = set(dset.data_vars.keys())
    if len(variables_to_keep_) > 0:
        selected_variables = set(dset.data_vars.keys()) & variables_to_keep_
    selected_variables = selected_variables - variables_to_skip_
    if len(set(dset.data_vars.keys())) != len(selected_variables):
        return dset[selected_variables]
    return dset


def preprocess_wrf(
    dset: xr.Dataset, variables_to_keep, variables_to_skip
) -> xr.Dataset:
    """Preprocess WRF dataset."""
    dset = rename_coords(dset)
    dset = change_dims(dset)
    dset = add_projection(dset)
    dset = choose_variables(dset, variables_to_keep, variables_to_skip)
    return dset


class WrfDriver(AbstractBaseDriver):
    """Driver class for netCDF files."""

    name = "wrf_driver"
    version = "0.1a0"

    def __init__(
        self,
        path: str,
        metadata: dict,
        pattern: str | None = None,
        field_id: str | None = None,
        metadata_caching: bool = False,
        metadata_cache_path: str | None = None,
        storage_options: dict | None = None,
        xarray_kwargs: dict | None = None,
        mapping: dict[str, dict[str, str]] | None = None,
        load_files_on_persistance: bool = True,
        variables_to_keep: str | list[str] | None = None,
        variables_to_skip: str | list[str] | None = None,
    ) -> None:
        super().__init__(metadata=metadata)
        self.path = path
        self.pattern = pattern
        self.field_id = field_id
        self.metadata_caching = metadata_caching
        self.metadata_cache_path = metadata_cache_path
        self.storage_options = storage_options
        self.mapping = mapping
        self.xarray_kwargs = xarray_kwargs or {}
        self.load_files_on_persistance = load_files_on_persistance
        self.preprocess = partial(
            preprocess_wrf,
            variables_to_keep=variables_to_keep,
            variables_to_skip=variables_to_skip,
        )

    @property
    def _arguments(self) -> dict:
        return {
            "path": self.path,
            "id_pattern": self.field_id,
            "metadata_caching": self.metadata_caching,
            "metadata_cache_path": self.metadata_cache_path,
            "mapping": self.mapping,
        } | self.xarray_kwargs

    def read(self) -> Dataset | DataCube:
        """Read netCDF."""
        if self.pattern:
            return open_dataset(
                pattern=self.pattern,
                preprocess=self.preprocess,
                **self._arguments,
            )
        return open_datacube(
            delay_read_cubes=True,
            preprocess=self.preprocess,
            **self._arguments,
        )

    def load(self) -> Dataset | DataCube:
        """Load netCDF."""
        if self.pattern:
            return open_dataset(pattern=self.pattern, **self._arguments)
        return open_datacube(delay_read_cubes=False, **self._arguments)
