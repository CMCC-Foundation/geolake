# from . import __version__
import os

import geokube
from dask.delayed import Delayed
from intake.source.base import DataSource, Schema
from geokube.core.datacube import DataCube
from geokube.core.dataset import Dataset


# xarray_kwargs keys NOT forwarded to the metadata build:
# - `combine`/`concat_dim` are passed to build_metadata_cache explicitly;
# - `parallel` (an open_mfdataset flag), `engine`, `scheduler` are build/opener controls
#   the build handles itself or does not accept as opener kwargs;
# - `preprocess` is a read-time transform the build intentionally never applies;
# - `drop_variables` is a read-time *exclusion* filter, not a *materialization* flag
#   (unlike decode_times/mask_and_scale, which bake values into the store and so must be
#   symmetric). An excluded var can be dropped at read from a store that still contains it
#   (a harmless lazy reference). Forwarding it to the build gains nothing and hits
#   VirtualiZarr's STRICT drop_vars, which raises when the var is absent from a given file
#   (e.g. `time_bnds` present in only some bioclimind files). The read path still forwards
#   it (xarray's drop is lenient), so exclusion still happens -- transparently.
_BUILD_ONLY_XARRAY_KWARGS = frozenset(
    {"combine", "concat_dim", "parallel", "engine", "scheduler", "preprocess",
     "drop_variables"}
)


class GeokubeSource(DataSource):
    """Common behaviours for plugins in this repo"""

    version = "0.1a0"
    container = "geokube"
    partition_access = True

    def _build_open_kwargs(self) -> dict:
        """Opener kwargs (``decode_times``, ``mask_and_scale``, ``chunks``, ...) forwarded
        from the catalog's ``xarray_kwargs`` to ``build_metadata_cache`` so the BUILD
        decodes data exactly like the read-path open does.

        Dropping them (the historical behaviour) broke the build<->read symmetry the cache
        design relies on: e.g. a source configured with ``decode_times: false`` still had its
        cache built with default decoding and crashed on files whose time is undecodable or
        out-of-range (the soil-erosion ``time_bnds`` fill-sentinel case). geokube persists the
        safe subset in the store and the reader replays it, so the cache stays transparent.
        Build-only / non-opener keys are excluded.
        """
        return {
            k: v for k, v in (self.xarray_kwargs or {}).items()
            if k not in _BUILD_ONLY_XARRAY_KWARGS
        }

    @staticmethod
    def _cache_mode() -> str:
        """Caching role for this process.

        ``build`` is opt-in via the ``CACHE_MODE`` environment variable and is
        only ever set on the dedicated catalog/build container (which owns write
        access to the cache). Everything else defaults to ``read``, so the API
        and executors can never (re)build or invalidate the metadata cache.
        """
        return os.environ.get("CACHE_MODE", "read")

    @staticmethod
    def _cache_progress() -> bool:
        """Show geokube's cache-build progress bars (tqdm) while building.

        Opt-in via the ``CACHE_PROGRESS`` environment variable; only meaningful
        on the catalog/build container (progress is used solely while
        (re)building the cache -- API/executor never reach the build branch).
        Off by default.
        """
        return os.environ.get("CACHE_PROGRESS", "").strip().lower() in (
            "1", "true", "yes", "y", "t", "on"
        )

    def _maybe_build_metadata_cache(self) -> None:
        """(Re)build the kerchunk metadata cache, only in build mode.

        No-op in read mode or for sources with ``metadata_caching`` disabled.
        Builds for any cached source -- including single, non-glob resources:
        geokube's caching openers are read-only and raise ``CacheNotExist`` when
        the cache is missing, so the cache must be published before any read.
        After this returns, the regular read path (``metadata_caching=True``)
        loads exactly what was just published, validating the round-trip.
        """
        if (
            self._cache_mode() != "build"
            or not self.metadata_caching
        ):
            return
        geokube.build_metadata_cache(
            path=self.path,
            pattern=self.pattern,
            metadata_cache_path=self.metadata_cache_path,
            id_pattern=self.field_id,
            mapping=self.mapping,
            # Recombine at open time the same way the direct open would; the
            # catalog encodes the strategy in xarray_kwargs (default by_coords).
            combine=self.xarray_kwargs.get("combine", "by_coords"),
            concat_dim=self.xarray_kwargs.get("concat_dim"),
            progress=self._cache_progress(),
            # Forward the opener kwargs (decode_times, mask_and_scale, ...) so the build
            # decodes exactly like the read path -- keeping the cache transparent.
            **self._build_open_kwargs(),
        )

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