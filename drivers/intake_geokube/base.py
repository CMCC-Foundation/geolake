"""Module with AbstractBaseDriver definition."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from dask.delayed import Delayed
from geokube.core.datacube import DataCube
from geokube.core.dataset import Dataset
from intake.source.base import DataSourceBase

from .queries.geoquery import GeoQuery

_NOT_SET: str = "<NOT_SET>"


class AbstractBaseDriver(ABC, DataSourceBase):
    """Abstract base class for all GeoLake-related drivers."""

    name: str = _NOT_SET
    version: str = _NOT_SET
    container: str = "python"
    log: logging.Logger

    def __new__(cls, *arr, **kw):  # pylint: disable=unused-argument
        """Create a new instance of driver and configure logger."""
        obj = super().__new__(cls)
        assert (
            obj.name != _NOT_SET
        ), f"'name' class attribute was not set for the driver '{cls}'"
        assert (
            obj.version != _NOT_SET
        ), f"'name' class attribute was not set for the driver '{cls}'"
        obj.log = cls.__configure_logger()
        return obj

    def __init__(self, *, metadata: dict) -> None:
        super().__init__(metadata=metadata)

    @classmethod
    def __configure_logger(cls) -> logging.Logger:
        log = logging.getLogger(f"geolake.intake.{cls.__name__}")
        level = os.environ.get("GeoLake_LOG_LEVEL", "INFO")
        logformat = os.environ.get(
            "GeoLake_LOG_FORMAT",
            "%(asctime)s %(name)s %(funcName)s %(levelname)s %(message)s",
        )
        log.setLevel(level)  # type: ignore[arg-type]
        for handler in log.handlers:
            if isinstance(handler, logging.StreamHandler):
                break
        else:
            log.addHandler(logging.StreamHandler())
        if logformat:
            formatter = logging.Formatter(logformat)
            for handler in log.handlers:
                handler.setFormatter(formatter)
        for handler in log.handlers:
            handler.setLevel(level)  # type: ignore[arg-type]
        return log

    @abstractmethod
    def read(self) -> Any:
        """Read metadata."""
        raise NotImplementedError

    @abstractmethod
    def load(self) -> Any:
        """Read metadata and load data into the memory."""
        raise NotImplementedError

    def process(self, query: GeoQuery) -> Any:
        """
        Process data with the query.

        Parameters
        ----------
        query: `queries.GeoQuery`
            A query to use for data processing

        Results
        -------
        res: Any
            Result of `query` processing

        Examples
        --------
        ```python
        >>> data = catalog['dataset']['product'].process(query)
        ```
        """
        data_ = self.read()
        return self._process_geokube_dataset(data_, query=query, compute=True)

    def _process_geokube_dataset(
        self,
        dataset: Dataset | DataCube,
        query: GeoQuery,
        compute: bool = False,
    ) -> Dataset | DataCube:
        self.log.info(
            "processing geokube structure with Geoquery: %s '", query
        )
        if not query:
            self.log.info("query is empty!")
            return dataset.compute() if compute else dataset
        if isinstance(dataset, Dataset):
            self.log.info("filtering with: %s", query.filters)
            dataset = dataset.filter(**query.filters)
        if isinstance(dataset, Delayed) and compute:
            dataset = dataset.compute()
        if query.variable:
            self.log.info("selecting variable: %s", query.variable)
            dataset = dataset[query.variable]
        if query.area:
            self.log.info("subsetting by bounding box: %s", query.area)
            dataset = dataset.geobbox(**query.area)
        if query.location:
            self.log.info("subsetting by location: %s", query.location)
            dataset = dataset.locations(**query.location)
        if query.time:
            self.log.info("subsetting by time: %s", query.time)
            dataset = dataset.sel(time=query.time)
        if query.vertical:
            self.log.info("subsetting by vertical: %s", query.vertical)
            method = None if isinstance(query.vertical, slice) else "nearest"
            dataset = dataset.sel(vertical=query.vertical, method=method)
        if isinstance(dataset, Dataset) and compute:
            self.log.info(
                "computing delayed datacubes in the dataset with %d"
                " records...",
                len(dataset),
            )
            dataset = dataset.apply(
                lambda dc: dc.compute() if isinstance(dc, Delayed) else dc
            )
        return dataset
