# from . import __version__
from dask.delayed import Delayed
from intake.source.base import DataSource, Schema
from geokube.core.datacube import DataCube
from geokube.core.dataset import Dataset



class GeokubeSource(DataSource):
    """Common behaviours for plugins in this repo"""

    version = "0.1a0"
    container = "geokube"
    partition_access = True

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