"""geokube driver for intake."""
import logging
from typing import Mapping, Optional
from .base import GeokubeSource
import geokube
from geokube.core.datacube import DataCube
from geokube.core.errs import CacheNotExist
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

    def _open_main(self):
        """Open the main time-series files.

        With ``metadata_caching`` the expensive multi-file open is served from the
        kerchunk cache published by the catalog: read-only by default, and only
        (re)built when ``CACHE_MODE=build`` (catalog/build container). A missing
        cache raises ``CacheNotExist`` instead of silently rebuilding. The few
        ancillary files are cheap and opened directly (see ``_open_dataset``).
        """
        if not self.metadata_caching:
            return xr.open_mfdataset(glob.glob(self.path), **self.xarray_kwargs)

        if self._cache_mode() == "build":
            # NSIDC files concat along the bare index dim `tdim` (no coordinate),
            # so build with the catalog's combine spec (nested + concat_dim=tdim).
            geokube.build_metadata_cache(
                path=self.path,
                pattern=None,
                metadata_cache_path=self.metadata_cache_path,
                combine=self.xarray_kwargs.get("combine", "by_coords"),
                concat_dim=self.xarray_kwargs.get("concat_dim"),
                progress=self._cache_progress(),
            )

        from geokube.backend import _kerchunk

        payload = _kerchunk.load_store(self.metadata_cache_path)
        if payload is None:
            raise CacheNotExist(
                f"No metadata cache at `{self.metadata_cache_path}`. The catalog"
                " must build it (CACHE_MODE=build) before read-only access."
            )
        return _kerchunk.open_store(payload)

    def _open_dataset(self):
        ds = self._open_main()
        afilepaths = glob.glob(self.ancillary_path)
        ancillary = xr.open_mfdataset(afilepaths, compat='override')
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
        return self._kube
