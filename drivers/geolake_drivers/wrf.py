"""geokube driver for intake."""
import logging
from functools import partial
from typing import Any, Mapping, Optional, Union

import numpy as np
import xarray as xr

from .base import GeokubeSource
from geokube import open_datacube, open_dataset


_DIM_RENAME_MAP = {
    "Time": "time",
    "south_north": "latitude",
    "west_east": "longitude",
}
_COORD_RENAME_MAP = {"XTIME": "time", "XLAT": "latitude", "XLONG": "longitude"}
_COORD_SQUEEZE_NAMES = ("latitude", "longitude")
_PROJECTION = {"grid_mapping_name": "latitude_longitude"}


def _cast_to_set(item: Any):
    if item is None:
        return set()
    if isinstance(item, set):
        return item
    if isinstance(item, str):
        return {item}
    if isinstance(item, list):
        return set(item)
    raise TypeError(f"type '{type(item)}' is not supported!")


def rename_coords(dset: xr.Dataset, **kwargs) -> xr.Dataset:
    """Rename coordinates"""
    dset_ = dset.rename_vars(_COORD_RENAME_MAP)
    # Removing `Time` dimension from latitude and longitude.
    coords = dset_.coords
    for name in _COORD_SQUEEZE_NAMES:
        coord = dset_[name]
        if "Time" in coord.dims:
            coords[name] = coord.squeeze(dim="Time", drop=True)
    return dset_


def change_dims(dset: xr.Dataset, **kwargs) -> xr.Dataset:
    """Changes dimensions to time, latitude, and longitude"""
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


def add_projection(dset: xr.Dataset, **kwargs) -> xr.Dataset:
    """Add projection information to the dataset"""
    coords = dset.coords
    coords["crs"] = xr.DataArray(data=np.array(1), attrs=_PROJECTION)
    for var in dset.data_vars.values():
        enc = var.encoding
        enc["grid_mapping"] = "crs"
        # TODO: Check if this is needed. This code renames coordinates stored
        # in encoding from `'XLONG XLAT XTIME'` to `'longitude latitude time'`.
        if coord_names := enc.get("coordinates"):
            for old_name, new_name in _COORD_RENAME_MAP.items():
                coord_names = coord_names.replace(old_name, new_name)
            enc["coordinates"] = coord_names
    return dset


def choose_variables(
    dset: xr.Dataset,
    variables_to_keep: Optional[Union[str, list[str]]] = None,
    variables_to_skip: Optional[Union[str, list[str]]] = None,
    **kwargs,
) -> xr.Dataset:
    """Choose only some variables by keeping or skipping some of them"""
    variables_to_keep = _cast_to_set(variables_to_keep)
    variables_to_skip = _cast_to_set(variables_to_skip)
    selected_variables = set(dset.data_vars.keys())
    if len(variables_to_keep) > 0:
        selected_variables = set(dset.data_vars.keys()) & variables_to_keep
    selected_variables = selected_variables - variables_to_skip
    if len(set(dset.data_vars.keys())) != len(selected_variables):
        return dset[selected_variables]
    return dset


def preprocess_wrf(dset: xr.Dataset, **kwargs) -> xr.Dataset:
    """Preprocess WRF dataset"""
    dset = rename_coords(dset, **kwargs)
    dset = change_dims(dset)
    dset = add_projection(dset, **kwargs)
    dset = choose_variables(dset, **kwargs)
    return dset


class WRFSource(GeokubeSource):
    name = "wrf"

    def __init__(
        self,
        path: str,
        pattern: str = None,
        field_id: str = None,
        delay_read_cubes: bool = False,
        metadata_caching: bool = False,
        metadata_cache_path: str = None,
        storage_options: dict = None,
        xarray_kwargs: dict = None,
        metadata=None,
        mapping: Optional[Mapping[str, Mapping[str, str]]] = None,
        load_files_on_persistance: Optional[bool] = True,
        variables_to_keep: Optional[Union[str, list[str]]] = None,
        variables_to_skip: Optional[Union[str, list[str]]] = None,
        **kwargs
    ):
        self._kube = None
        self.path = path
        self.pattern = pattern
        self.field_id = field_id
        self.delay_read_cubes = delay_read_cubes
        self.metadata_caching = metadata_caching
        self.metadata_cache_path = metadata_cache_path
        self.storage_options = storage_options
        self.mapping = mapping
        self.xarray_kwargs = {} if xarray_kwargs is None else xarray_kwargs
        self.load_files_on_persistance = load_files_on_persistance
        self.preprocess = partial(
            preprocess_wrf,
            variables_to_keep=variables_to_keep,
            variables_to_skip=variables_to_skip,
        )
        #     self.xarray_kwargs.update({'engine' : 'netcdf'})
        super(WRFSource, self).__init__(metadata=metadata, **kwargs)

    def _open_dataset(self):
        if self.pattern is None:
            self._kube = open_datacube(
                path=self.path,
                id_pattern=self.field_id,
                metadata_caching=self.metadata_caching,
                metadata_cache_path=self.metadata_cache_path,
                mapping=self.mapping,
                **self.xarray_kwargs,
                preprocess=self.preprocess,
            )
        else:
            self._kube = open_dataset(
                path=self.path,
                pattern=self.pattern,
                id_pattern=self.field_id,
                delay_read_cubes=self.delay_read_cubes,
                metadata_caching=self.metadata_caching,
                metadata_cache_path=self.metadata_cache_path,
                mapping=self.mapping,
                **self.xarray_kwargs,
                preprocess=self.preprocess,
            )
        return self._kube
