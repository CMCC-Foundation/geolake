"""NetCDF driver for GeoLake."""

from geokube import open_datacube, open_dataset
from geokube.core.datacube import DataCube
from geokube.core.dataset import Dataset

from ..base import AbstractBaseDriver


class NetCdfDriver(AbstractBaseDriver):
    """Driver class for netCDF files."""

    name = "netcdf_driver"
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
        """Read netCDF into geokube.Dataset or geokube.Datacube.

        If `pattern` is set for a product, the method would return
        a `geokube.Dataset` with `dask.Delayed` objects instead of 
        `geokube.DataCube`s.
        
        Returns
        -------
        cube : `geokube.Dataset` or `geokube.DataCube`
        
        Examples
        --------
        ```python
        >>> data = catalog['era5']['reanalysis'].read()
        ```
        """
        if self.pattern:
            return open_dataset(
                pattern=self.pattern, delay_read_cubes=True, **self._arguments
            )
        return open_datacube(**self._arguments)

    def load(self) -> Dataset | DataCube:
        """Load netCDF into geokube.Dataset or geokube.Datacube.

        All cubes would be computed on loading.
        
        Returns
        -------
        cube : `geokube.Dataset` or `geokube.DataCube`
        
        Examples
        --------
        ```python
        >>> data = catalog['era5']['reanalysis'].read()
        ```
        """
        if self.pattern:
            return open_dataset(
                pattern=self.pattern, delay_read_cubes=False, **self._arguments
            )
        return open_datacube(**self._arguments)
