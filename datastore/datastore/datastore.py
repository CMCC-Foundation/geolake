"""Module for catalog management classes and functions"""
from __future__ import annotations

import os
import logging
import json

import intake
from dask.delayed import Delayed

from intake_geokube.queries.geoquery import GeoQuery

from geokube.core.datacube import DataCube
from geokube.core.dataset import Dataset

from .singleton import Singleton
from .util import log_execution_time
from .const import BaseRole
from .exception import UnauthorizedError

DEFAULT_MAX_REQUEST_SIZE_GB = 10


class Datastore(metaclass=Singleton):
    """Singleton component for managing catalog data"""

    _LOG = logging.getLogger("geokube.Datastore")

    def __init__(self) -> None:
        if "CATALOG_PATH" not in os.environ:
            self._LOG.error(
                "missing required environment variable: 'CATALOG_PATH'"
            )
            raise KeyError(
                "Missing required environment variable: 'CATALOG_PATH'"
            )
        if "CACHE_PATH" not in os.environ:
            self._LOG.error(
                "'CACHE_PATH' environment variable was not set. catalog will"
                " not be opened!"
            )
            raise RuntimeError(
                "'CACHE_PATH' environment variable was not set. catalog will"
                " not be opened!"
            )
        self.catalog = intake.open_catalog(os.environ["CATALOG_PATH"])
        self.cache_dir = os.environ["CACHE_PATH"]
        self._LOG.info("cache dir set to %s", self.cache_dir)
        self.cache = None

    @log_execution_time(_LOG)
    def get_cached_product_or_read(
        self, dataset_id: str, product_id: str, query: GeoQuery | None = None
    ) -> DataCube | Dataset:
        """Get product from the cache instead of loading files indicated in
        the catalog if `metadata_caching` set to `True`.
        If might return `geokube.DataCube` or `geokube.Dataset`.

        Parameters
        -------
        dataset_id : str
            ID of the dataset
        product_id : str
            ID of the dataset

        Returns
        -------
        kube : DataCube or Dataset
        """
        if self.cache is None:
            self._load_cache()
        if (
            dataset_id not in self.cache
            or product_id not in self.cache[dataset_id]
        ):
            self._LOG.info(
                "dataset `%s` or product `%s` not found in cache! Reading"
                " product!",
                dataset_id,
                product_id,
            )
            return self.catalog(CACHE_DIR=self.cache_dir)[dataset_id][
                product_id
            ].process(query=query)
        return self.cache[dataset_id][product_id]

    @log_execution_time(_LOG)
    def _load_cache(self, datasets: list[str] | None = None):
        if self.cache is None or datasets is None:
            self.cache = {}
            datasets = self.dataset_list()

        for i, dataset_id in enumerate(datasets):
            self._LOG.info(
                "loading cache for `%s` (%d/%d)",
                dataset_id,
                i + 1,
                len(datasets),
            )
            self.cache[dataset_id] = {}
            for product_id in self.product_list(dataset_id):
                catalog_entry = self.catalog(CACHE_DIR=self.cache_dir)[
                    dataset_id
                ][product_id]
                if hasattr(catalog_entry, "metadata_caching") and not catalog_entry.metadata_caching:
                    self._LOG.info(
                        "`metadata_caching` for product %s.%s set to `False`",
                        dataset_id,
                        product_id,
                    )
                    continue
                try:
                    self.cache[dataset_id][
                        product_id
                    ] = catalog_entry.read()
                except ValueError:
                    self._LOG.error(
                        "failed to load cache for `%s.%s`",
                        dataset_id,
                        product_id,
                        exc_info=True,
                    ) 
                except NotImplementedError:
                    pass

    @log_execution_time(_LOG)
    def dataset_list(self) -> list:
        """Get list of datasets available in the catalog stored in `catalog`
        attribute

        Returns
        -------
        datasets : list
            List of datasets present in the catalog
        """
        datasets = set(self.catalog(CACHE_DIR=self.cache_dir))
        datasets -= {
            "medsea-rea-e3r1",
        }
        # NOTE: medsae cmip uses cftime.DatetimeNoLeap as time
        # need to think how to handle it
        return sorted(list(datasets))

    @log_execution_time(_LOG)
    def product_list(self, dataset_id: str):
        """Get list of products available in the catalog for dataset
        indicated by `dataset_id`

        Parameters
        ----------
        dataset_id : str
            ID of the dataset

        Returns
        -------
        products : list
            List of products for the dataset
        """
        return list(self.catalog(CACHE_DIR=self.cache_dir)[dataset_id])

    @log_execution_time(_LOG)
    def dataset_info(self, dataset_id: str):
        """Get information about the dataset and names of all available
        products (with their metadata)

        Parameters
        ----------
        dataset_id : str
            ID of the dataset

        Returns
        -------
        info : dict
            Dict of short information about the dataset
        """
        info = {}
        entry = self.catalog(CACHE_DIR=self.cache_dir)[dataset_id]
        if entry.metadata:
            info["metadata"] = entry.metadata
            info["metadata"]["id"] = dataset_id
        info["products"] = {}
        for product_id in entry:
            prod_entry = entry[product_id]
            info["products"][product_id] = prod_entry.metadata
            info["products"][product_id][
                "description"
            ] = prod_entry.description
        return info

    @log_execution_time(_LOG)
    def product_metadata(self, dataset_id: str, product_id: str):
        """Get product metadata directly from the catalog.

        Parameters
        ----------
        dataset_id : str
            ID of the dataset
        product_id : str
            ID of the product

        Returns
        -------
        metadata : dict
            DatasetMetadata of the product
        """
        return self.catalog(CACHE_DIR=self.cache_dir)[dataset_id][
            product_id
        ].metadata

    @log_execution_time(_LOG)
    def first_eligible_product_details(
        self,
        dataset_id: str,
        role: str | list[str] | None = None,
        use_cache: bool = False,
    ):
        """Get details for the 1st product of the dataset eligible for the `role`.
        If `role` is `None`, the `public` role is considered.

        Parameters
        ----------
        dataset_id : str
            ID of the dataset
        role : optional str or list of str, default=`None`
            Role code for which the 1st eligible product of a dataset
            should be selected
        use_cache : bool, optional, default=False
            Data will be loaded from cache if set to `True` or directly
            from the catalog otherwise

        Returns
        -------
        details : dict
            Details of the product

        Raises
        ------
        UnauthorizedError
            if none of product of the requested dataset is eligible for a role
        """
        info = {}
        product_ids = self.product_list(dataset_id)
        for prod_id in product_ids:
            if not self.is_product_valid_for_role(
                dataset_id, prod_id, role=role
            ):
                continue
            entry = self.catalog(CACHE_DIR=self.cache_dir)[dataset_id][prod_id]
            if entry.metadata:
                info["metadata"] = entry.metadata
            info["description"] = entry.description
            info["id"] = prod_id
            info["dataset"] = self.dataset_info(dataset_id=dataset_id)
            if use_cache:
                info["data"] = self.get_cached_product_or_read(
                    dataset_id, prod_id
                ).to_dict()
            else:
                info["data"] = entry.read_chunked().to_dict()
            return info
        raise UnauthorizedError()

    @log_execution_time(_LOG)
    def product_details(
        self,
        dataset_id: str,
        product_id: str,
        role: str | list[str] | None = None,
        use_cache: bool = False,
    ):
        """Get details for the single product

        Parameters
        ----------
        dataset_id : str
            ID of the dataset
        product_id : str
            ID of the product
        role : optional str or list of str, default=`None`
            Role code for which the the product is requested.
        use_cache : bool, optional, default=False
            Data will be loaded from cache if set to `True` or directly
            from the catalog otherwise

        Returns
        -------
        details : dict
            Details of the product

        Raises
        ------
        UnauthorizedError
            if the requested product is not eligible for a role
        """
        info = {}
        if not self.is_product_valid_for_role(
            dataset_id, product_id, role=role
        ):
            raise UnauthorizedError()
        entry = self.catalog(CACHE_DIR=self.cache_dir)[dataset_id][product_id]
        if entry.metadata:
            info["metadata"] = entry.metadata
        info["description"] = entry.description
        info["id"] = product_id
        info["dataset"] = self.dataset_info(dataset_id=dataset_id)
        if use_cache:
            info["data"] = self.get_cached_product_or_read(
                dataset_id, product_id
            ).to_dict()
        else:
            info["data"] = entry.read_chunked().to_dict()
        return info

    def product_info(
        self, dataset_id: str, product_id: str, use_cache: bool = False
    ):
        info = {}
        entry = self.catalog(CACHE_DIR=self.cache_dir)[dataset_id][product_id]
        if entry.metadata:
            info["metadata"] = entry.metadata
        if use_cache:
            info["data"] = self.get_cached_product_or_read(
                dataset_id, product_id
            ).to_dict()
        else:
            info["data"] = entry.read_chunked().to_dict()
        return info

    @log_execution_time(_LOG)
    def query(
        self,
        dataset_id: str,
        product_id: str,
        query: GeoQuery | dict | str,
        compute: None | bool = False,
    ) -> DataCube:
        """Query dataset

        Parameters
        ----------
        dataset_id : str
            ID of the dataset
        product_id : str
            ID of the product
        query : GeoQuery or dict or str or bytes or bytearray
            Query to be executed for the given product
        compute : bool, optional, default=False
            If True, resulting data of DataCube will be computed, otherwise
            DataCube with `dask.Delayed` object will be returned

        Returns
        -------
        kube : DataCube
            DataCube processed according to `query`
        """
        self._LOG.debug("query: %s", query)
        geoquery: GeoQuery = GeoQuery.parse(query)
        self._LOG.debug("processing GeoQuery: %s", geoquery)
        # NOTE: we always use catalog directly and single product cache
        self._LOG.debug("loading product...")
        kube = self.catalog(CACHE_DIR=self.cache_dir)[dataset_id][
            product_id
        ].process(query=geoquery)
        return kube

    @log_execution_time(_LOG)
    def estimate(
        self,
        dataset_id: str,
        product_id: str,
        query: GeoQuery | dict | str,
    ) -> int:
        """Estimate dataset size

        Parameters
        ----------
        dataset_id : str
            ID of the dataset
        product_id : str
            ID of the product
        query : GeoQuery or dict or str
            Query to be executed for the given product

        Returns
        -------
        size : int
            Number of bytes of the estimated kube
        """
        self._LOG.debug("query: %s", query)
        geoquery: GeoQuery = GeoQuery.parse(query)
        self._LOG.debug("processing GeoQuery: %s", geoquery)
        # NOTE: we always use catalog directly and single product cache
        self._LOG.debug("loading product...")
        # NOTE: for estimation we use cached products
        kube = self.get_cached_product_or_read(dataset_id, product_id, 
                                               query=query)
        return Datastore._process_query(kube, geoquery, False).nbytes

    @log_execution_time(_LOG)
    def is_product_valid_for_role(
        self,
        dataset_id: str,
        product_id: str,
        role: str | list[str] | None = None,
    ):
        entry = self.catalog(CACHE_DIR=self.cache_dir)[dataset_id][product_id]
        product_role = BaseRole.PUBLIC
        if entry.metadata:
            product_role = entry.metadata.get("role", BaseRole.PUBLIC)
        if product_role == BaseRole.PUBLIC:
            return True
        if not role:
            # NOTE: it means, we consider the public profile
            return False
        if BaseRole.ADMIN in role:
            return True
        if product_role in role:
            return True
        return False

    @staticmethod
    def _process_query(kube, query: GeoQuery, compute: None | bool = False):
        if isinstance(kube, Dataset):
            Datastore._LOG.debug("filtering with: %s", query.filters)
            try:
                kube = kube.filter(**query.filters)
            except ValueError as err:
                Datastore._LOG.warning("could not filter by one of the key: %s", err)
        if isinstance(kube, Delayed) and compute:
            kube = kube.compute()
        if query.variable:
            Datastore._LOG.debug("selecting fields...")
            kube = kube[query.variable]
        if query.area:
            Datastore._LOG.debug("subsetting by geobbox...")
            kube = kube.geobbox(**query.area)
        if query.location:
            Datastore._LOG.debug("subsetting by locations...")
            kube = kube.locations(**query.location)
        if query.time:
            Datastore._LOG.debug("subsetting by time...")
            kube = kube.sel(time=query.time)
        if query.vertical:
            Datastore._LOG.debug("subsetting by vertical...")
            method = None if isinstance(query.vertical, slice) else "nearest"
            kube = kube.sel(vertical=query.vertical, method=method)
        return kube.compute() if compute else kube
