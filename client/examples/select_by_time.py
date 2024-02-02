import geolake
c = geolake.Client()
c.retrieve("era5-single-levels", "reanalysis",
    {
        "variable": "total_precipitation",
        "year": [2002, 2003],
        "month": [10, 11],
        "day": [1, 2, 3, 31],
        "hour": ["12:00"],
        "location": [52.56, 8.45],
        "format": "netcdf",
    },
    "select_by_time_result.nc",
)