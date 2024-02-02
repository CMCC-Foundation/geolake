# from . import __version__
from dask.delayed import Delayed
from intake.source.base import DataSource, Schema
from geokube.core.datacube import DataCube
from geokube.core.dataset import Dataset

from .geoquery import GeoQuery



class GeokubeSource(DataSource):
    """Common behaviours for plugins in this repo"""

    version = "0.1a0"
    container = "geokube"
    partition_access = True
    geoquery: GeoQuery | None
    compute: bool

    def __init__(self, metadata, geoquery: GeoQuery = None, compute: bool = False):
        super().__init__(metadata=metadata)
        self.geoquery = geoquery
        self.compute = compute

    def _get_schema(self):
        """Make schema object, which embeds goekube fields metadata"""

        if self._kube is None:
            self._open_dataset()
            # TODO: Add schema for Geokube Dataset
            if isinstance(self._kube, DataCube):
                metadata = {
                    "fields": {
                        k: {
                            "dims": list(self._kube[k].dim_names),
                            #                                    'axis': list(self._kube[k].dims_axis_names),
                            "coords": list(self._kube[k].coords.keys()),
                        }
                        for k in self._kube.fields.keys()
                    },
                }
                metadata.update(self._kube.properties)
                self._schema = Schema(
                    datashape=None,
                    dtype=None,
                    shape=None,
                    npartitions=None,
                    extra_metadata=metadata,
                )
            # TODO: Add schema for Geokube Dataset
            if isinstance(self._kube, Dataset):
                self._schema = Schema(
                    datashape=None,
                    dtype=None,
                    shape=None,
                    npartitions=None,
                    extra_metadata={},
                )

        return self._schema

    def read(self):
        """Return an in-memory geokube"""
        self._load_metadata()
        # TODO: Implement load in memory
        return self._kube

    def read_chunked(self):
        """Return a lazy geokube object"""
        return self.read()
    
    def read_partition(self, i):
        """Fetch one chunk of data at tuple index i"""
        raise NotImplementedError

    def to_dask(self):
        """Return geokube object where variables (fields/coordinates) are dask arrays
        """
        return self.read_chunked()

    def to_pyarrow(self):
        """Return an in-memory pyarrow object"""
        raise NotImplementedError

    def close(self):
        """Delete open file from memory"""
        self._kube = None
        self._schema = None

    def process_with_query(self):
        self.read_chunked()
        if not self.geoquery:
            return self._kube.compute() if self.compute else self._kube
        if isinstance(self._kube, Dataset):
            self._kube = self._kube.filter(**self.geoquery.filters)
        if isinstance(self._kube, Delayed) and self.compute:
            self._kube = self._kube.compute()
        if self.geoquery.variable:
            self._kube = self._kube[self.geoquery.variable]
        if self.geoquery.area:
            self._kube = self._kube.geobbox(**self.geoquery.area)
        if self.geoquery.location:
            self._kube = self._kube.locations(**self.geoquery.location)
        if self.geoquery.time:
            self._kube = self._kube.sel(time=self.geoquery.time)
        if self.geoquery.vertical:
            method = None if isinstance(self.geoquery.vertical, slice) else "nearest"
            self._kube = self._kube.sel(vertical=self.geoquery.vertical, method=method)
        return self._kube.compute() if self.compute else self._kube                
 