import geolake
c = geolake.Client()
c.retrieve("era5-single-levels",  "reanalysis",
    {
        "variable": "10_metre_u_wind_component",
        "time": {"start": "2002-01-01", "stop": "2003-12-31"},
        "location": [52.56, 8.45],
        "format": "netcdf",
    },
    "select_by_date_slice_result.nc",
)
