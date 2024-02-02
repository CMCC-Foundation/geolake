import geolake
c = geolake.Client()
c.retrieve("e-obs", "ensemble",
    {
        "variable": "thickness_of_rainfall_amount",
        "ensemble_statistic": "mean",  # Attribute
        "resolution": "0.25",  # Attribute
        "version": "v21.0e",  # Attribute
        "time": {"start": "2002-01-01", "stop": "2002-12-31"},
        "format": "netcdf",
    },
    "e-obs.nc",
)
