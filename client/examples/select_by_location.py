import geolake
c = geolake.Client()
c.retrieve("era5-single-levels", "reanalysis",
    {
        "variable": "total_precipitation",
        "time": {"start": "2002-01-01", "stop": "2005-01-10"},
        "location": [52.56, 8.45],
        "format": "netcdf",
    },
    "select_by_location_result.nc",
)
