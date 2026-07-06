"""Integration: Datastore hides products whose metadata cache is not built.

`is_product_available` distinguishes the three cache states on a small nested
catalog (mirroring the real catalog.yaml -> sub-catalog -> products layout) built
on the committed synthetic.nc fixture. Run in-image (needs geokube + the
geokube_netcdf driver).
"""
import os
import shutil

import pytest

pytest.importorskip("geokube")
pytestmark = pytest.mark.integration

import intake  # noqa: E402

from datastore.datastore import Datastore  # noqa: E402
from datastore.singleton import Singleton  # noqa: E402

_SYNTHETIC = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "drivers",
        "tests",
        "resources",
        "synthetic.nc",
    )
)

_MAIN_YAML = """
metadata:
  version: 0.1
  parameters:
    CACHE_DIR:
      type: str
      default: %s
sources:
  ds1:
    driver: yaml_file_cat
    args:
      path: "{{ CATALOG_DIR }}/ds1.yaml"
"""

_DS1_YAML = """
sources:
  proda:
    driver: geokube_netcdf
    args: { path: "{{ CATALOG_DIR }}/synthetic.nc", metadata_caching: false }
  prodb:
    driver: geokube_netcdf
    args: { path: "{{ CATALOG_DIR }}/synthetic.nc", metadata_caching: true, metadata_cache_path: "{{ CACHE_DIR }}/prodb.cache" }
  prodc:
    driver: geokube_netcdf
    args: { path: "{{ CATALOG_DIR }}/synthetic.nc", metadata_caching: true, metadata_cache_path: "{{ CACHE_DIR }}/prodc.cache" }
"""


@pytest.fixture(autouse=True)
def _reset_singleton():
    # The Datastore is a Singleton bound to CATALOG_PATH/CACHE_PATH at first use;
    # clear it around this test so it picks up the temp catalog and does not leak
    # into (or inherit from) other tests.
    Singleton._instances.clear()
    yield
    Singleton._instances.clear()


def test_is_product_available_by_cache_state(tmp_path, monkeypatch):
    cat_dir = tmp_path / "catalog"
    cat_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    shutil.copy(_SYNTHETIC, cat_dir / "synthetic.nc")
    (cat_dir / "main.yaml").write_text(_MAIN_YAML % str(cache_dir))
    (cat_dir / "ds1.yaml").write_text(_DS1_YAML)
    main = str(cat_dir / "main.yaml")

    # Build phase (catalog/build container role): publish ONLY prodb's cache.
    monkeypatch.setenv("CACHE_MODE", "build")
    intake.open_catalog(main)(CACHE_DIR=str(cache_dir))["ds1"]["prodb"].read()

    # Read phase (api/executor role): load what is available.
    monkeypatch.setenv("CACHE_MODE", "read")
    monkeypatch.setenv("CATALOG_PATH", main)
    monkeypatch.setenv("CACHE_PATH", str(cache_dir))
    store = Datastore()
    store._load_cache()

    # metadata_caching=False -> always available (read directly).
    assert store.is_product_available("ds1", "proda") is True
    # metadata_caching=True with cache built -> available.
    assert store.is_product_available("ds1", "prodb") is True
    # metadata_caching=True but cache missing (CacheNotExist) -> hidden.
    assert store.is_product_available("ds1", "prodc") is False
