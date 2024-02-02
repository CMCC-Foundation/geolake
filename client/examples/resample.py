import geolake
c = geolake.Client()
c.retrieve("era5-single-levels", "reanalysis",
    {
        "variable": "2_metre_temperature",
        "time": {"start": "2001-01-01", "stop": "2005-01-01"},
        "area": {"north": 47.2, "south": 36.5, "west": 6.5, "east": 18.5},
        "format": "netcdf",
        "resample": {"operator": "mean", "frequency": "1M", "closed": "right"},
    },
    "resample_result.nc",
)
