"""Regenerate the committed synthetic test fixture `synthetic.nc`.

Run once (needs xarray + a netCDF backend, e.g. inside the geolake-datastore image):

    python drivers/tests/resources/make_synthetic.py

Produces a small, deterministic CF-compliant NetCDF used by the geokube
integration test (`drivers/tests/test_driver_roundtrip.py`) via
`synthetic_catalog.yaml`. The field is analytic (not random) so the file is
reproducible and compresses well.
"""
import os

import numpy as np
import xarray as xr

NT, NLAT, NLON = 10, 100, 100


def build_dataset() -> xr.Dataset:
    lat = np.linspace(30.0, 60.0, NLAT)
    lon = np.linspace(-10.0, 40.0, NLON)
    time = np.array(
        [np.datetime64("2020-01-01") + np.timedelta64(d, "D") for d in range(NT)]
    )
    # Deterministic, temperature-like field: spatial pattern + per-step offset.
    spatial = (
        273.15
        + 15.0 * np.cos(np.radians(lat))[:, None]
        + 5.0 * np.sin(np.radians(lon))[None, :]
    )  # (NLAT, NLON)
    t2m = (spatial[None, :, :] + np.arange(NT)[:, None, None]).astype("float32")

    ds = xr.Dataset(
        {"t2m": (("time", "latitude", "longitude"), t2m)},
        coords={"time": time, "latitude": lat, "longitude": lon},
    )
    ds["latitude"].attrs = {"standard_name": "latitude", "units": "degrees_north"}
    ds["longitude"].attrs = {"standard_name": "longitude", "units": "degrees_east"}
    ds["t2m"].attrs = {"standard_name": "air_temperature", "units": "K"}
    return ds


def main() -> None:
    out = os.path.join(os.path.dirname(__file__), "synthetic.nc")
    build_dataset().to_netcdf(
        out, encoding={"t2m": {"zlib": True, "complevel": 4}}
    )
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
