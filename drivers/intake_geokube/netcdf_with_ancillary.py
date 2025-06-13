"""geokube driver for intake."""
import logging
from typing import Mapping, Optional
from .base import GeokubeSource
from geokube import open_dataset, open_datacube
from geokube.core.datacube import DataCube
import pickle
import os
import xarray as xr
import numpy as np
import glob

_PROJECTION = {"grid_mapping_name": "latitude_longitude"}

class NetCDFAncillarySource(GeokubeSource):
    name = "geokube_netcdf_ancillary"

    def add_projection(self, dset: xr.Dataset, **kwargs) -> xr.Dataset:
        """Add projection information to the dataset"""
        coords = dset.coords
        coords["crs"] = xr.DataArray(data=np.array(1), attrs=_PROJECTION)
        for var in dset.data_vars.values():
            enc = var.encoding
            enc["grid_mapping"] = "crs"
        return dset

    def __init__(
        self,
        path: str,
        ancillary_path: str,
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
        **kwargs
    ):
        self._kube = None
        self.path = path
        self.ancillary_path = ancillary_path
        self.pattern = pattern
        self.field_id = field_id
        self.delay_read_cubes = delay_read_cubes
        self.metadata_caching = metadata_caching
        self.metadata_cache_path = metadata_cache_path
        self.storage_options = storage_options
        self.mapping = mapping
        self.xarray_kwargs = {} if xarray_kwargs is None else xarray_kwargs
        self.load_files_on_persistance = load_files_on_persistance
        #        self.xarray_kwargs.update({'engine' : 'netcdf'})
        super(NetCDFAncillarySource, self).__init__(metadata=metadata, **kwargs)

    def _open_dataset(self):

        if self.metadata_caching:
            cached = None
            if os.path.exists(self.metadata_cache_path):
                with open(self.metadata_cache_path, "rb") as f:
                    cached = pickle.load(f)
                self._kube = cached
                return self._kube

        afilepaths = glob.glob(self.ancillary_path)
        filepaths = glob.glob(self.path)
        ancillary = xr.open_mfdataset(afilepaths, compat='override')
        ds = xr.open_mfdataset(filepaths, **self.xarray_kwargs)
        finalds = xr.merge([ancillary, ds])

        finalds.xgrid.attrs['standard_name'] = 'projection_grid_x_centers'
        finalds.ygrid.attrs['standard_name'] = 'projection_grid_y_centers'

        finalds2 = self.add_projection(finalds)
        finalds3 = finalds2.assign_coords(tdim=np.arange(finalds2.sizes['tdim']))
        time = finalds3.time.values
        finalds4 = finalds3.assign_coords(time=("tdim", time)).swap_dims({"tdim": "time"})
        finalds5 = finalds4.sortby("time")

        for var in finalds5.data_vars.values():
            if "grid_mapping" in var.attrs:
                del var.attrs["grid_mapping"]

        self._kube = DataCube.from_xarray(finalds5, mapping=self.mapping)

        if self.metadata_caching:
            with open(self.metadata_cache_path, "wb") as f:
                pickle.dump(self._kube, f)

        return self._kube
