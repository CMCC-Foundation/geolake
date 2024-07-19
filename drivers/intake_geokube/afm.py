"""geokube driver for intake."""
import logging
from functools import partial
from typing import Any, Mapping, Optional, Union

import numpy as np
import xarray as xr

from .base import GeokubeSource
from geokube import open_datacube, open_dataset

from geokube.core.datacube import DataCube

_PROJECTION = {"grid_mapping_name": "latitude_longitude"}

def postprocess_afm(ds: xr.Dataset, post_process_chunks) -> xr.Dataset:
    latitude = ds['lat'].values
    longitude = ds['lon'].values
    # ds = ds.expand_dims(dim={"latitude": latitude, "longitude": longitude}, axis=(1,0))
    ds = ds.drop('lat')
    ds = ds.drop('lon')
    ds = ds.drop('certainty')
    deduplicated = ds.expand_dims(dim={"latitude": latitude, "longitude": longitude}, axis=(1, 0))
    for dim in ds.dims:
        indexes = {dim: ~deduplicated.get_index(dim).duplicated(keep='first')}
        deduplicated = deduplicated.isel(indexes)
    return add_projection(deduplicated.sortby('time').chunk(post_process_chunks))

def add_projection(dset: xr.Dataset, **kwargs) -> xr.Dataset:
    """Add projection information to the dataset"""
    coords = dset.coords
    coords["crs"] = xr.DataArray(data=np.array(1), attrs=_PROJECTION)
    for var in dset.data_vars.values():
        enc = var.encoding
        enc["grid_mapping"] = "crs"
    return dset

class CMCCAFMSource(GeokubeSource):
    name = "cmcc_afm_geokube"

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
            postprocess_chunk: Optional = None
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
        self.postprocess_chunk = postprocess_chunk
        # self.preprocess = preprocess_afm
        super(CMCCAFMSource, self).__init__(metadata=metadata)

    def _open_dataset(self):
        self._kube = DataCube.from_xarray(
            postprocess_afm(
                open_datacube(
                    path=self.path,
                    id_pattern=self.field_id,
                    metadata_caching=self.metadata_caching,
                    metadata_cache_path=self.metadata_cache_path,
                    mapping=self.mapping,
                    **self.xarray_kwargs,
                    # preprocess=self.preprocess
                ).to_xarray(),
                self.postprocess_chunk
            )
        )
        return self._kube
