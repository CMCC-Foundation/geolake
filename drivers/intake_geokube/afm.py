"""geokube driver for intake."""
import logging
from functools import partial
from typing import Any, Mapping, Optional, Union

import numpy as np
import xarray as xr

from .base import GeokubeSource
from geokube import open_datacube, open_dataset


def preprocess_afm(dset: xr.Dataset) -> xr.Dataset:
    return dset.to_dataframe().set_index(['lat', 'lon'], append=True).to_xarray()


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
        self.preprocess = preprocess_afm
        super(CMCCAFMSource, self).__init__(metadata=metadata)

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
