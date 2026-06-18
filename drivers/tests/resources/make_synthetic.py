"""Regenerate the committed synthetic test fixtures used by the geokube
integration tests (`drivers/tests/test_driver_roundtrip.py`).

Run once (needs xarray + a netCDF backend, e.g. inside the geolake-datastore image):

    python drivers/tests/resources/make_synthetic.py

All datasets are deterministic (analytic, not random) so the files are
reproducible and compress well. Each fixture is the RAW input that the
corresponding driver expects; the driver applies its own preprocessing
automatically when the source is read through the intake catalog.
"""
import os

import numpy as np
import xarray as xr

NT, NLAT, NLON = 10, 100, 100
_HERE = os.path.dirname(__file__)


def _time_days(n):
    return np.array(
        [np.datetime64("2020-01-01") + np.timedelta64(d, "D") for d in range(n)]
    )


# --- geokube_netcdf: plain CF NetCDF -------------------------------------
def build_netcdf_dataset() -> xr.Dataset:
    lat = np.linspace(30.0, 60.0, NLAT)
    lon = np.linspace(-10.0, 40.0, NLON)
    spatial = (
        273.15
        + 15.0 * np.cos(np.radians(lat))[:, None]
        + 5.0 * np.sin(np.radians(lon))[None, :]
    )
    t2m = (spatial[None, :, :] + np.arange(NT)[:, None, None]).astype("float32")
    ds = xr.Dataset(
        {"t2m": (("time", "latitude", "longitude"), t2m)},
        coords={"time": _time_days(NT), "latitude": lat, "longitude": lon},
    )
    ds["latitude"].attrs = {"standard_name": "latitude", "units": "degrees_north"}
    ds["longitude"].attrs = {"standard_name": "longitude", "units": "degrees_east"}
    ds["t2m"].attrs = {"standard_name": "air_temperature", "units": "K"}
    return ds


# --- cmcc_wrf_geokube: raw WRF-like layout --------------------------------
# preprocess_wrf renames XTIME/XLAT/XLONG -> time/latitude/longitude, collapses
# the 2D lat/lon to 1D and swaps dims Time/south_north/west_east -> time/lat/lon.
def build_wrf_dataset() -> xr.Dataset:
    nsn, nwe = NLAT, NLON
    lat1d = np.linspace(30.0, 60.0, nsn)
    lon1d = np.linspace(-10.0, 40.0, nwe)
    xlat = np.broadcast_to(lat1d[:, None], (nsn, nwe)).astype("float32")
    xlong = np.broadcast_to(lon1d[None, :], (nsn, nwe)).astype("float32")
    base = (
        273.15
        + 15.0 * np.cos(np.radians(lat1d))[None, :, None]
        + 5.0 * np.sin(np.radians(lon1d))[None, None, :]
    )
    t2 = (base + np.arange(NT)[:, None, None]).astype("float32")
    ds = xr.Dataset(
        {
            "T2": (("Time", "south_north", "west_east"), t2),
            "XLAT": (("south_north", "west_east"), xlat),
            "XLONG": (("south_north", "west_east"), xlong),
            "XTIME": (("Time",), _time_days(NT)),
        }
    )
    ds["T2"].attrs = {"standard_name": "air_temperature", "units": "K"}
    return ds


# --- geokube_netcdf_ancillary: main + ancillary files ---------------------
# The driver merges both, expecting xgrid/ygrid vars, a `tdim` dimension and a
# `time` var. Ancillary holds the static grid; main holds the time-varying data.
def build_ancillary_datasets():
    ny, nx = NLAT, NLON
    xgrid = np.linspace(0.0, 1000.0, nx).astype("float32")
    ygrid = np.linspace(0.0, 1000.0, ny).astype("float32")
    lat2d = np.broadcast_to(np.linspace(30.0, 60.0, ny)[:, None], (ny, nx)).astype("float32")
    lon2d = np.broadcast_to(np.linspace(-10.0, 40.0, nx)[None, :], (ny, nx)).astype("float32")

    ancillary = xr.Dataset(
        {
            "latitude": (("ygrid", "xgrid"), lat2d),
            "longitude": (("ygrid", "xgrid"), lon2d),
        },
        coords={"xgrid": ("xgrid", xgrid), "ygrid": ("ygrid", ygrid)},
    )
    ancillary["latitude"].attrs = {"standard_name": "latitude", "units": "degrees_north"}
    ancillary["longitude"].attrs = {"standard_name": "longitude", "units": "degrees_east"}

    base = (
        273.15
        + 15.0 * np.cos(np.radians(lat2d))
        + 5.0 * np.sin(np.radians(lon2d))
    )
    data = (base[None, :, :] + np.arange(NT)[:, None, None]).astype("float32")
    main = xr.Dataset(
        {"t2m": (("tdim", "ygrid", "xgrid"), data)},
        coords={
            "xgrid": ("xgrid", xgrid),
            "ygrid": ("ygrid", ygrid),
            "time": ("tdim", _time_days(NT)),
        },
    )
    main["t2m"].attrs = {"standard_name": "air_temperature", "units": "K"}
    return ancillary, main


def _write(ds, name, var):
    out = os.path.join(_HERE, name)
    ds.to_netcdf(out, encoding={var: {"zlib": True, "complevel": 4}})
    print("wrote", out, os.path.getsize(out), "bytes")


def main() -> None:
    _write(build_netcdf_dataset(), "synthetic.nc", "t2m")
    _write(build_wrf_dataset(), "synthetic_wrf.nc", "T2")
    anc, main_ds = build_ancillary_datasets()
    _write(anc, "synthetic_ancillary_coords.nc", "latitude")
    _write(main_ds, "synthetic_ancillary_main.nc", "t2m")


if __name__ == "__main__":
    main()
