"""Integration: validates OUR integration with geokube (geokube_netcdf driver)
on SYNTHETIC data (no dependencies on external datasets). Run in-image."""
import textwrap

import pytest

pytest.importorskip("geokube")
pytestmark = pytest.mark.integration

import numpy as np  # noqa: E402
import xarray as xr  # noqa: E402
import intake  # noqa: E402


def _make_cf_netcdf(path):
    ds = xr.Dataset(
        {"t2m": (("time", "latitude", "longitude"), np.random.rand(2, 3, 4))},
        coords={
            "time": np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[ns]"),
            "latitude": np.array([0.0, 1.0, 2.0]),
            "longitude": np.array([0.0, 1.0, 2.0, 3.0]),
        },
    )
    ds["latitude"].attrs = {"standard_name": "latitude", "units": "degrees_north"}
    ds["longitude"].attrs = {"standard_name": "longitude", "units": "degrees_east"}
    ds["t2m"].attrs = {"units": "K", "standard_name": "air_temperature"}
    ds.to_netcdf(path)


def test_geokube_netcdf_driver_reads_synthetic_data(tmp_path):
    nc = tmp_path / "synthetic.nc"
    _make_cf_netcdf(str(nc))
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        textwrap.dedent(
            f"""
            sources:
              synthetic:
                driver: geokube_netcdf
                args:
                  path: '{nc}'
                  delay_read_cubes: false
                  metadata_caching: false
            """
        )
    )
    catalog = intake.open_catalog(str(catalog_path))
    result = catalog["synthetic"].read()
    # open_datacube (no `pattern`) → DataCube; defensive in case of a Dataset.
    cube = result.cubes[0] if hasattr(result, "cubes") else result
    xc = cube.to_xarray()
    assert "t2m" in xc
