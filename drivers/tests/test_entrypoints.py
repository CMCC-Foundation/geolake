from importlib.metadata import entry_points


def test_intake_driver_entrypoints_registered():
    """intake scopre i driver via entry-points: verifichiamo i 3 attivi.

    geokube-free: legge solo i metadati, non importa i moduli driver.
    """
    names = {ep.name for ep in entry_points(group="intake.drivers")}
    assert {
        "geokube_netcdf",
        "cmcc_wrf_geokube",
        "geokube_netcdf_ancillary",
    } <= names
    # `sentinel` è un prototipo non funzionante → NON registrato.
    assert "cmcc_sentinel_geokube" not in names
