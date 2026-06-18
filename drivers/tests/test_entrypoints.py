from importlib.metadata import entry_points


def test_intake_driver_entrypoints_registered():
    """intake discovers drivers via entry-points: we verify the 3 active ones.

    geokube-free: reads only the metadata, does not import the driver modules.
    """
    names = {ep.name for ep in entry_points(group="intake.drivers")}
    assert {
        "geokube_netcdf",
        "cmcc_wrf_geokube",
        "geokube_netcdf_ancillary",
    } <= names
    # `sentinel` is a non-working prototype → NOT registered.
    assert "cmcc_sentinel_geokube" not in names
