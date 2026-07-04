"""Integration: validates OUR integration with geokube for the registered intake
drivers, on committed SYNTHETIC fixtures (no external datasets). Run in-image.

The drivers apply their own preprocessing automatically when read through the
intake catalog; the fixtures in resources/ are the RAW input each driver expects.
Regenerate the NetCDF fixtures with resources/make_synthetic.py.

`afm` (cmcc_afm_geokube) and `sentinel` are intentionally not tested: unregistered
prototype drivers, to be rewritten."""
import os

import pytest

pytest.importorskip("geokube")
pytestmark = pytest.mark.integration

import intake  # noqa: E402

_RESOURCES = os.path.join(os.path.dirname(__file__), "resources")
_GRID = 10 * 100 * 100
_WRF = os.path.join(_RESOURCES, "synthetic_wrf.nc")


def _read_to_xarray(source_name):
    catalog = intake.open_catalog(
        os.path.join(_RESOURCES, "synthetic_catalog.yaml")
    )
    result = catalog[source_name].read()
    # DataCube for the single-cube sources here; defensive in case of a Dataset.
    cube = result.cubes[0] if hasattr(result, "cubes") else result
    return cube.to_xarray()


def test_geokube_netcdf_driver_reads_synthetic_data():
    xc = _read_to_xarray("synthetic")
    assert "t2m" in xc
    # Robust to coordinate renaming by geokube: total element count is preserved.
    assert xc["t2m"].size == _GRID


def test_wrf_driver_reads_synthetic_data():
    xc = _read_to_xarray("synthetic_wrf")
    assert "T2" in xc
    assert xc["T2"].size == _GRID


def test_ancillary_driver_reads_synthetic_data():
    xc = _read_to_xarray("synthetic_ancillary")
    assert "t2m" in xc
    assert xc["t2m"].size == _GRID


def test_wrf_driver_caching_roundtrip(tmp_path, monkeypatch):
    """WRF preprocessing must also be applied on the metadata-cache read path.

    geokube's cached opener builds the cube straight from the raw kerchunk store;
    the upstream fix applies `preprocess` before DataCube assembly so the cached
    cube matches the direct open (dims time/latitude/longitude, not the raw
    Time/south_north/west_east). This is the production WRF scenario
    (metadata_caching=True). The `pattern` path is fixed transitively in geokube
    (open_dataset builds each group via open_datacube).
    """
    from intake_geokube.wrf import CMCCWRFSource

    cache_path = str(tmp_path / "wrf.cache")

    # Build phase: only the catalog/build container publishes the cache.
    monkeypatch.setenv("CACHE_MODE", "build")
    CMCCWRFSource(
        path=_WRF, metadata_caching=True, metadata_cache_path=cache_path
    )._maybe_build_metadata_cache()

    # Read phase: read-only role (api/executor) loads the published cache.
    monkeypatch.setenv("CACHE_MODE", "read")
    result = CMCCWRFSource(
        path=_WRF, metadata_caching=True, metadata_cache_path=cache_path
    ).read()
    cube = result.cubes[0] if hasattr(result, "cubes") else result
    xc = cube.to_xarray()

    assert "T2" in xc
    assert xc["T2"].size == _GRID
    assert {"time", "latitude", "longitude"} <= set(xc.sizes)


def _write_broken_time_bnds(path):
    """A file whose ``time`` is a decodable ``days since`` unit but whose ``time_bnds``
    carries an int32 fill sentinel (``-2147483648``) with no units of its own — the
    soil-erosion-vhr-era5 ``historical`` shape. Default CF decoding overflows on it;
    ``decode_times=False`` is the only correct handling (the catalog config sets it)."""
    import numpy as np
    import xarray as xr

    ds = xr.Dataset(
        {"v": (("time", "y", "x"), np.zeros((1, 3, 4), dtype="float32")),
         "time_bnds": (("time", "bnds"),
                       np.array([[0.0, -2147483648.0]], dtype="float64"))},
        coords={"time": ("time", np.array([5297.0], dtype="float64")),
                "y": ("y", np.arange(3)), "x": ("x", np.arange(4))},
    )
    ds["time"].attrs = {"units": "days since 1991-01-01", "calendar": "proleptic_gregorian",
                        "standard_name": "time", "axis": "T", "bounds": "time_bnds"}
    ds["time"].encoding = {"_FillValue": None}
    ds["time_bnds"].encoding = {"_FillValue": None}
    ds.to_netcdf(str(path), engine="netcdf4", format="NETCDF4")
    return str(path)


def test_decode_times_kwarg_forwarded_to_build(tmp_path, monkeypatch):
    """Opener flags in ``xarray_kwargs`` (here ``decode_times``) must reach the metadata-cache
    BUILD, not just the read path. Before the fix the driver dropped them at build time, so a
    source configured with ``decode_times: false`` still built its cache with default decoding
    and crashed on undecodable/out-of-range time (the soil-erosion ``time_bnds`` fill sentinel).
    Forwarding them restores build<->read symmetry: the flag is persisted in the store and
    replayed on read, and the build no longer crashes.
    """
    import numpy as np
    from intake_geokube.netcdf import NetCDFSource
    from geokube.backend import _kerchunk

    p = _write_broken_time_bnds(tmp_path / "hist.nc")
    cache = str(tmp_path / "hist.cache")

    # Build phase: forwarding decode_times=False is what lets the build succeed at all.
    monkeypatch.setenv("CACHE_MODE", "build")
    NetCDFSource(
        path=p, metadata_caching=True, metadata_cache_path=cache,
        xarray_kwargs={"decode_times": False},
    )._maybe_build_metadata_cache()
    assert _kerchunk.load_store(cache)["open_kwargs"].get("decode_times") is False  # persisted

    # Read phase: reads the published cache; time stays raw (matches the configured open).
    monkeypatch.setenv("CACHE_MODE", "read")
    result = NetCDFSource(
        path=p, metadata_caching=True, metadata_cache_path=cache,
        xarray_kwargs={"decode_times": False},
    ).read()
    cube = result.cubes[0] if hasattr(result, "cubes") else result
    xc = cube.to_xarray()
    assert "v" in xc
    assert not np.issubdtype(np.asarray(xc["time"].values).dtype, np.datetime64)


def _write_no_time_bnds(path):
    """A file with a ``time`` axis but NO ``time_bnds`` — the bioclimind shape where a var
    named in drop_variables is absent from some files."""
    import numpy as np
    import xarray as xr

    ds = xr.Dataset(
        {"bio": (("time", "y", "x"), np.zeros((1, 3, 4), dtype="float32"))},
        coords={"time": ("time", np.array([0], dtype="int32")),
                "y": ("y", np.arange(3)), "x": ("x", np.arange(4))},
    )
    ds["time"].attrs = {"units": "days since 1970-01-01", "calendar": "standard",
                        "standard_name": "time", "axis": "T"}
    ds.to_netcdf(str(path), engine="netcdf4", format="NETCDF4")
    return str(path)


def test_drop_variables_not_forwarded_to_build(tmp_path, monkeypatch):
    """Regression (bioclimind): `drop_variables` naming a var absent from a file must not crash
    the build. `drop_variables` is a read-time EXCLUSION filter, not a build-materialization flag,
    so the driver keeps it read-only (it is NOT forwarded to build_metadata_cache, where
    VirtualiZarr's strict drop would raise on the missing var). The read path still forwards it and
    drops leniently, so the variable is excluded from the result all the same.
    """
    from intake_geokube.netcdf import NetCDFSource
    from geokube.backend import _kerchunk

    p = _write_no_time_bnds(tmp_path / "bio.nc")  # has 'time', no 'time_bnds'
    cache = str(tmp_path / "bio.cache")

    # Build must succeed even though the file lacks 'time_bnds' listed in drop_variables.
    monkeypatch.setenv("CACHE_MODE", "build")
    NetCDFSource(
        path=p, metadata_caching=True, metadata_cache_path=cache,
        xarray_kwargs={"drop_variables": ["time", "time_bnds"]},
    )._maybe_build_metadata_cache()
    assert _kerchunk.load_store(cache) is not None  # store published (no strict-drop crash)

    # Read: drop_variables is applied leniently at read -> 'time' excluded from the cube.
    monkeypatch.setenv("CACHE_MODE", "read")
    result = NetCDFSource(
        path=p, metadata_caching=True, metadata_cache_path=cache,
        xarray_kwargs={"drop_variables": ["time", "time_bnds"]},
    ).read()
    cube = result.cubes[0] if hasattr(result, "cubes") else result
    xc = cube.to_xarray()
    assert "bio" in xc
    assert "time_bnds" not in xc.variables
