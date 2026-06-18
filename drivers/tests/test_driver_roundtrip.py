"""Integration: validates OUR integration with geokube (geokube_netcdf driver)
on a committed SYNTHETIC dataset (no dependencies on external datasets).
Run in-image. The fixture is drivers/tests/resources/{synthetic.nc,synthetic_catalog.yaml}
(regenerate the NetCDF with resources/make_synthetic.py)."""
import os

import pytest

pytest.importorskip("geokube")
pytestmark = pytest.mark.integration

import intake  # noqa: E402

_RESOURCES = os.path.join(os.path.dirname(__file__), "resources")


def test_geokube_netcdf_driver_reads_synthetic_data():
    catalog = intake.open_catalog(
        os.path.join(_RESOURCES, "synthetic_catalog.yaml")
    )
    result = catalog["synthetic"].read()
    # open_datacube (no `pattern`) → DataCube; defensive in case of a Dataset.
    cube = result.cubes[0] if hasattr(result, "cubes") else result
    xc = cube.to_xarray()
    assert "t2m" in xc
    # Robust to coordinate renaming by geokube: total element count is preserved.
    assert xc["t2m"].size == 10 * 100 * 100
