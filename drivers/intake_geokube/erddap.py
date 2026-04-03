from erddapy import ERDDAP
import pandas as pd
import xarray as xr
import geokube 
import logging
from typing import Mapping, Optional
from .base import GeokubeSource

class ERDDAPSource(GeokubeSource):
    name = "geokube_erddap"

    def __init__(
        self,
        path: str,
        root: str ,
        time_range: str = None,
        lat_range: str = None,
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
        self.root = root
        self.time_range = time_range
        self.lat_range = lat_range
        self.metadata_caching = metadata_caching
        self.metadata_cache_path = metadata_cache_path
        self.storage_options = storage_options
        self.mapping = mapping
        self.xarray_kwargs = {} if xarray_kwargs is None else xarray_kwargs
        self.load_files_on_persistance = load_files_on_persistance
        #        self.xarray_kwargs.update({'engine' : 'netcdf'})
        super(ERDDAPSource, self).__init__(metadata=metadata, **kwargs)

    def open_ds(self,p,r):
        boolean_value = False
        e = ERDDAP(server = r) 
        info_df = e.get_search_url(search_for=p, response="csv")
        df = pd.read_csv(info_df)
        ds = {}
        e.protocol = "griddap"
        for i, row in df.iterrows():
            if pd.notna(row["griddap"]):
                try:
                    if(p in row["Title"]):
                        e.dataset_id = row["Dataset ID"]
                        info = e.get_info_url(response="csv")
                        info_df = pd.read_csv(info, header=None)
                        for y, riga in info_df.iterrows():
                            if(info_df[2][y]=="actual_range") and (info_df[1][y]=="time"):
                                if(info_df[4][y]!=self.time_range):
                                  boolean_value = True
                            if(info_df[2][y]=="actual_range") and (info_df[1][y]=="latitude"):
                                if(info_df[4][y]!=self.lat_range):
                                  boolean_value=True
                            if(boolean_value==True):
                                break
                        if(boolean_value==False):
                            ds[i] = xr.open_dataset(row["griddap"], **self.xarray_kwargs) 
                        else:
                            boolean_value=False
                except Exception as ex:
                    raise TypeError(f"Error on dataset {row['Dataset ID']}: {ex}")
        final_dataset = xr.merge([ds[k] for k in ds if ds[k] is not None], compat="override")
        return geokube.core.datacube.DataCube.from_xarray(final_dataset)
    
    def _open_dataset(self):
        self._kube=self.open_ds(self.path,self.root)
        return self._kube