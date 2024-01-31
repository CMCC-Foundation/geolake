import os
import pytest
import intake
import yaml


@pytest.fixture
def e_obs_catalog_path():
    yield os.path.join("tests", "resources", "test_catalog.yaml")


def test_mapping_1(e_obs_catalog_path):
    catalog = intake.open_catalog(e_obs_catalog_path)
    ds = catalog["ensemble-spread"].read()
    for cb in ds.cubes:
        for f in cb.values():
            assert "my_lat" in f.domain._coords
        xcb = cb.to_xarray()
        assert "my_lat" in xcb
        assert "latitude" not in xcb
        assert "longitude" in xcb
        assert "time" in xcb
        assert "new_feature" in xcb.my_lat.attrs
        assert xcb.my_lat.attrs["new_feature"] == "new_val"
