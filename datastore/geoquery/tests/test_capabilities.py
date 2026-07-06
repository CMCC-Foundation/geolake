"""Tests for per-product capability metadata and query enforcement.

These are pure pydantic/logic tests (no geokube, no catalog), so they run on
the bare runner like ``test_geoquery.py``.
"""
from geoquery.geoquery import GeoQuery
from geoquery.capabilities import (
    DatasetCapabilities,
    FORMAT_REGISTRY,
    GRID_REGISTRY,
    RESAMPLE_FREQ_REGISTRY,
    RESAMPLE_OP_REGISTRY,
)


# --- registries ----------------------------------------------------------
def test_format_registry_includes_zarr():
    assert set(FORMAT_REGISTRY) == {"netcdf", "geojson", "zarr", "zarr3"}
    assert FORMAT_REGISTRY["zarr"] == {"label": "Zarr", "ext": ".zarr"}
    # zarr3 shares the ``.zarr`` extension (see capabilities.py for why).
    assert FORMAT_REGISTRY["zarr3"] == {"label": "Zarr v3", "ext": ".zarr"}


def test_other_registries():
    assert set(GRID_REGISTRY) == {"native", "regular"}
    assert set(RESAMPLE_FREQ_REGISTRY) == {"1D", "1ME", "1Y"}
    assert set(RESAMPLE_OP_REGISTRY) == {"mean", "max", "min", "sum", "median"}


# --- from_metadata defaults / tolerance ----------------------------------
def test_defaults_reproduce_historical_behavior():
    caps = DatasetCapabilities()
    assert caps.temporal_subset is True
    assert caps.spatial_subset is True
    assert caps.vertical_subset is True
    assert caps.variable_raw_labels is False
    assert caps.format.values == ["netcdf"]
    assert caps.regrid.enabled is False
    assert caps.resample.enabled is False


def test_from_metadata_none_empty_and_missing_key():
    for meta in (None, {}, {"role": "public"}, {"capabilities": None}):
        caps = DatasetCapabilities.from_metadata(meta)
        assert caps == DatasetCapabilities()


def test_from_metadata_malformed_block_falls_back_to_defaults():
    assert DatasetCapabilities.from_metadata(
        {"capabilities": "nope"}
    ) == DatasetCapabilities()


def test_from_metadata_invalid_values_falls_back_to_defaults():
    # `format.values` must be a list; an invalid block must not raise (it would
    # otherwise 500 the unauthenticated estimate path).
    caps = DatasetCapabilities.from_metadata(
        {"capabilities": {"format": {"values": {"not": "a list"}}}}
    )
    assert caps == DatasetCapabilities()


def test_from_metadata_partial_block():
    caps = DatasetCapabilities.from_metadata(
        {"capabilities": {"spatial_subset": False, "variable_raw_labels": True}}
    )
    assert caps.spatial_subset is False
    assert caps.variable_raw_labels is True
    # untouched keys keep their defaults
    assert caps.temporal_subset is True
    assert caps.format.values == ["netcdf"]


# --- check(): permissive defaults -----------------------------------------
def test_default_caps_allow_full_subset_query():
    caps = DatasetCapabilities()
    query = GeoQuery(
        variable=["t2m"],
        area={"north": 1, "south": 0, "east": 1, "west": 0},
        time={"start": "2020-01-01", "stop": "2020-02-01"},
        vertical=5.0,
        format="netcdf",
    )
    assert caps.check(query) == []


# --- check(): spatial -----------------------------------------------------
def test_spatial_disabled_rejects_area():
    caps = DatasetCapabilities(spatial_subset=False)
    query = GeoQuery(area={"north": 1, "south": 0, "east": 1, "west": 0})
    assert len(caps.check(query)) == 1


def test_spatial_disabled_rejects_location():
    caps = DatasetCapabilities(spatial_subset=False)
    query = GeoQuery(location={"latitude": 10, "longitude": 25})
    assert len(caps.check(query)) == 1


def test_spatial_disabled_allows_query_without_spatial():
    caps = DatasetCapabilities(spatial_subset=False)
    assert caps.check(GeoQuery(variable=["t2m"])) == []


# --- check(): temporal / vertical ----------------------------------------
def test_temporal_disabled_rejects_time():
    caps = DatasetCapabilities(temporal_subset=False)
    query = GeoQuery(time={"start": "2020-01-01", "stop": "2020-02-01"})
    assert len(caps.check(query)) == 1


def test_vertical_disabled_rejects_vertical():
    caps = DatasetCapabilities(vertical_subset=False)
    assert len(caps.check(GeoQuery(vertical=5.0))) == 1


# --- check(): regrid ------------------------------------------------------
def test_regrid_disabled_rejects_native_too():
    # 'native' is a datastore no-op but must still be rejected when the product
    # does not expose regridding at all.
    caps = DatasetCapabilities()
    assert len(caps.check(GeoQuery(regrid="native"))) == 1
    assert len(caps.check(GeoQuery(regrid="regular"))) == 1


def test_regrid_enabled_allows_known_value():
    caps = DatasetCapabilities(regrid={"enabled": True})
    assert caps.check(GeoQuery(regrid="regular")) == []
    assert caps.check(GeoQuery(regrid="native")) == []


def test_regrid_enabled_rejects_unknown_value():
    caps = DatasetCapabilities(regrid={"enabled": True})
    assert len(caps.check(GeoQuery(regrid="bogus"))) == 1


# --- check(): resample ----------------------------------------------------
def test_resample_disabled_rejects_resample():
    caps = DatasetCapabilities()
    query = GeoQuery(resample={"frequency": "1D", "operator": "mean"})
    assert len(caps.check(query)) == 1


def test_resample_empty_dict_is_not_a_violation():
    caps = DatasetCapabilities()
    assert caps.check(GeoQuery(resample={})) == []


def test_resample_enabled_allows_known_values():
    caps = DatasetCapabilities(resample={"enabled": True})
    query = GeoQuery(resample={"frequency": "1ME", "operator": "mean"})
    assert caps.check(query) == []


def test_resample_enabled_rejects_unknown_frequency():
    caps = DatasetCapabilities(resample={"enabled": True})
    query = GeoQuery(resample={"frequency": "1W", "operator": "mean"})
    assert len(caps.check(query)) == 1


def test_resample_enabled_rejects_unknown_operator():
    caps = DatasetCapabilities(resample={"enabled": True})
    query = GeoQuery(resample={"frequency": "1D", "operator": "std"})
    assert len(caps.check(query)) == 1


# --- check(): format ------------------------------------------------------
def test_default_format_rejects_geojson():
    caps = DatasetCapabilities()
    assert len(caps.check(GeoQuery(format="geojson"))) == 1


def test_format_none_is_allowed():
    caps = DatasetCapabilities()
    assert caps.check(GeoQuery(variable=["t2m"])) == []


def test_declared_formats_allow_value():
    caps = DatasetCapabilities(format={"values": ["netcdf", "geojson"]})
    assert caps.check(GeoQuery(format="geojson")) == []


def test_zarr_format_gated_by_values():
    assert len(DatasetCapabilities().check(GeoQuery(format="zarr"))) == 1
    caps = DatasetCapabilities(format={"values": ["netcdf", "zarr"]})
    assert caps.check(GeoQuery(format="zarr")) == []


def test_zarr3_format_gated_by_values():
    assert len(DatasetCapabilities().check(GeoQuery(format="zarr3"))) == 1
    caps = DatasetCapabilities(format={"values": ["netcdf", "zarr3"]})
    assert caps.check(GeoQuery(format="zarr3")) == []


# --- check(): variable_raw_labels is presentation-only --------------------
def test_variable_raw_labels_not_enforced():
    caps = DatasetCapabilities(variable_raw_labels=True)
    assert caps.check(GeoQuery(variable=["t2m"])) == []


# --- check(): multiple violations accumulate ------------------------------
def test_multiple_violations_accumulate():
    caps = DatasetCapabilities(spatial_subset=False, temporal_subset=False)
    query = GeoQuery(
        area={"north": 1, "south": 0, "east": 1, "west": 0},
        time={"start": "2020-01-01", "stop": "2020-02-01"},
        format="geojson",
    )
    assert len(caps.check(query)) == 3
