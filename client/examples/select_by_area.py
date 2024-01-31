import geolake
c = geolake.Client()
c.retrieve("era5-single-levels", "reanalysis",
    {
        "variable": ["2_metre_temperature", "total_precipitation"],
        "time": {"start": "2001-01-01", "stop": "2001-01-03"},
        "area": {"north": 47.2, "south": 36.5, "west": -6.5, "east": 18.5},
        "format": "netcdf",
    },
    "select_by_area.nc",
)
