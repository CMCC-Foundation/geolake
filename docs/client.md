# Geolake Python Client

GeoLake Python Client is a tool that enables users to interact with Geolake API.
To start, download the client using PyPI repository:

``` { .python  }
pip install geolake
```

Afterwards, you need to specify `.geolakerc` file in your home directory. It should contain url to the Geolake API and secrete user key:

``` 
url: <geolake_api_url>
key: <api-key>
```


Then, you can retrieve data as in the below example:


``` { .python .annotate .copy }
import geolake  # (1)

c = geolake.Client()  # (2)!

c.retrieve(  # (3)!
    "era5-single-levels",  # (4)!
    "reanalysis",  # (5)!
    { # (6)!
        "variable": "total_precipitation",  # (7)!
        "time": {"start": "2002-01-01", "stop": "2005-01-10"},  # (8)!
        "location": [52.56, 8.45],  # (9)!
        "format": "netcdf",  # (10)!
    }, # (11)!
    "select_by_location_result.nc",  # (12)!
)
```


1.  First, we import the `geolake` package.
2.  Then, you need to create an instance of `geolake.Client` class.
3.  To query a dataset, we are going to use `retrieve` method.
4.  1st argument is a dataset ID.
5.  2nd argument should be a product ID.
6.  3rd argument is a query itself.
7.  In the query, we can define a list of variables to retrieve...
8.  ... time cover specified as a range or time-combo: `"time": {"year": [2020]}`...
9.  ... locations to get (specified as latitude and longitude).
10.  You can specify format. Currently only **netcdf** is supported (or **zip** in case of any netCDF files).
11.  If a dataset has some custom attributes, you can specify them in the query.
12.  At the end, you specify the name of the downloaded file.

## Selecting bounding area
To select bounding area, you need to specify north and south values for latitude and west and east - for longitude:

``` { .python .annotate .copy }
import geolake

c = geolake.Client() 

c.retrieve( 
    "era5-single-levels", 
    "reanalysis", 
    { 
        "area": {"north": 47.2, "south": 36.5, "west": -6.5, "east": 18.5},
        "format": "netcdf", 
    }, 
    "select_by_area_result.nc", 
)
```

## Subsetting by time combo
Geolake supports selecting particular hours, days, months, and years. To do so,
specify a dictionary for `"time"` key in the following way:

``` { .python .annotate .copy }
import geolake

c = geolake.Client() 

c.retrieve( 
    "era5-single-levels", 
    "reanalysis", 
    { 
        "time": {
            "year": [2002, 2003],
            "month": [10, 11],
            "day": [1, 2, 3, 31],
            "hour": ["12:00"],
        },
        "format": "netcdf", 
    }, 
    "select_by_timecombo_result.nc", 
)
```
