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
