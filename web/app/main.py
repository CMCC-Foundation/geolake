"""Endpoints for `web` component"""
__version__ = "2.0"
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from geoquery.geoquery import GeoQuery

from aioprometheus import Counter, Summary, timer, MetricsMiddleware
from aioprometheus.asgi.starlette import metrics

from .access import AccessManager
from .models import ListOfDatasets, ListOfRequests
from .requester import GeokubeAPIRequester
from .widget import WidgetFactory
from .exceptions import (
    AuthenticationFailed,
    GeokubeAPIRequestFailed,
)
from .utils.numeric import prepare_estimate_size_message

app = FastAPI(
    title="geokube-dds API for Webportal",
    description="REST API for DDS Webportal",
    version=__version__,
    contact={
        "name": "geokube Contributors",
        "email": "geokube@googlegroups.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    root_path=os.environ.get("ENDPOINT_PREFIX", "/web"),
    on_startup=[GeokubeAPIRequester.init],
)

# ======== CORS ========= #
# TODO: origins should be limited!
ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======== Prometheus metrics ========= #
app.add_middleware(MetricsMiddleware)
app.add_route("/metrics", metrics)

app.state.request_time = Summary(
    "request_processing_seconds", "Time spent processing request"
)
app.state.request = Counter("request_total", "Total number of requests")

# ======== Endpoints definitions ========= #
@app.get("/")
async def dds_info():
    """Return current version of the DDS API for the Webportal"""
    return f"DDS Webportal API {__version__}"


@app.get("/datasets")
@timer(app.state.request_time, labels={"route": "GET /datasets"})
async def get_datasets(
    authorization: Optional[str] = Header(None, convert_underscores=True),
):
    """Get list of eligible datasets for the home page of the Webportal"""
    app.state.request.inc({"route": "GET /datasets"})
    try:
        user_credentials = AccessManager.retrieve_credentials_from_jwt(
            authorization
        )
        datasets = GeokubeAPIRequester.get(
            url="/datasets", user_credentials=user_credentials
        )
    except AuthenticationFailed as err:
        raise HTTPException(
            status_code=401, detail="User could not be authenticated"
        ) from err
    except GeokubeAPIRequestFailed as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    else:
        return ListOfDatasets.from_details(datasets)


@app.get("/datasets/{dataset_id}/{product_id}")
@timer(
    app.state.request_time,
    labels={"route": "GET /datasets/{dataset_id}/{product_id}"},
)
async def get_details_product(
    dataset_id: str,
    product_id: str,
    authorization: Optional[str] = Header(None, convert_underscores=True),
):
    """Get details for Webportal"""
    app.state.request.inc({"route": "GET /datasets/{dataset_id}/{product_id}"})
    try:
        user_credentials = AccessManager.retrieve_credentials_from_jwt(
            authorization
        )
        details = GeokubeAPIRequester.get(
            url=f"/datasets/{dataset_id}/{product_id}",
            user_credentials=user_credentials,
        )
    except AuthenticationFailed as err:
        raise HTTPException(
            status_code=401, detail="User could not be authenticated"
        ) from err
    except GeokubeAPIRequestFailed as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    else:
        return WidgetFactory(details).widgets


@app.post("/datasets/{dataset_id}/{product_id}/execute")
@timer(
    app.state.request_time,
    labels={"route": "POST /datasets/{dataset_id}/{product_id}/execute"},
)
async def execute(
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
    format: Optional[str] = "netcdf",
    authorization: Optional[str] = Header(None, convert_underscores=True),
):
    """Schedule the job of data retrieving by using geokube-dds API"""
    # TODO: remove below code after changing Webportal
    # In execute endpoint format query param is missing ( ...?format=netcdf)
    format = query.filters.pop("format", "netcdf")
    # ##########################################
    app.state.request.inc(
        {"route": "POST /datasets/{dataset_id}/{product_id}/execute"}
    )
    try:
        user_credentials = AccessManager.retrieve_credentials_from_jwt(
            authorization
        )
        response = GeokubeAPIRequester.post(
            url=f"/datasets/{dataset_id}/{product_id}/execute?format={format}",
            data=query.json(),
            user_credentials=user_credentials,
        )
    except AuthenticationFailed as err:
        raise HTTPException(
            status_code=401, detail="User could not be authenticated"
        ) from err
    except GeokubeAPIRequestFailed as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    else:
        return response


@app.post("/datasets/{dataset_id}/{product_id}/estimate")
@timer(
    app.state.request_time,
    labels={"route": "POST /datasets/{dataset_id}/{product_id}/estimate"},
)
async def estimate(
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
    authorization: Optional[str] = Header(None, convert_underscores=True),
):
    """Estimate the resulting size of the query by using geokube-dds API"""
    # TODO: remove below code after changing Webportal
    # In estimate endpoint format query param is missing ( ...?format=netcdf)
    query.filters.pop("format", None)
    # ##########################################
    app.state.request.inc(
        {"route": "POST /datasets/{dataset_id}/{product_id}/estimate"}
    )
    try:
        user_credentials = AccessManager.retrieve_credentials_from_jwt(
            authorization
        )
        response = GeokubeAPIRequester.post(
            url=f"/datasets/{dataset_id}/{product_id}/estimate?unit=GB",
            data=query.json(),
            user_credentials=user_credentials,
        )
        metadata = GeokubeAPIRequester.get(
            url=f"/datasets/{dataset_id}/{product_id}/metadata",
            user_credentials=user_credentials,
        )
    except AuthenticationFailed as err:
        raise HTTPException(
            status_code=401, detail="User could not be authenticated"
        ) from err
    except GeokubeAPIRequestFailed as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    else:
        return prepare_estimate_size_message(
            maximum_allowed_size_gb=metadata.get("maximum_query_size_gb", 10),
            estimated_size_gb=response.get("value"),
        )


# TODO: !!!access should be restricted!!!
@app.get("/get_api_key")
async def get_api_key(
    authorization: Optional[str] = Header(None, convert_underscores=True),
):
    """Get API key for a user the given Authorization token"""
    try:
        user_credentials = AccessManager.retrieve_credentials_from_jwt(
            authorization
        )
    except AuthenticationFailed as err:
        raise HTTPException(
            status_code=401, detail="User could not be authenticated"
        ) from err
    except GeokubeAPIRequestFailed as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    else:
        return {"key": f"{user_credentials.id}:{user_credentials.key}"}


@app.get("/requests")
@timer(app.state.request_time, labels={"route": "GET /requests"})
async def get_requests(
    authorization: Optional[str] = Header(None, convert_underscores=True),
):
    """Get requests for a user the given Authorization token"""
    app.state.request.inc({"route": "GET /requests"})
    try:
        user_credentials = AccessManager.retrieve_credentials_from_jwt(
            authorization
        )
        response_json = GeokubeAPIRequester.get(
            url="/requests", user_credentials=user_credentials
        )
    except AuthenticationFailed as err:
        raise HTTPException(
            status_code=401, detail="User could not be authenticated"
        ) from err
    except GeokubeAPIRequestFailed as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    else:
        requests = ListOfRequests(data=response_json)
        requests.add_requests_url_prefix(
            os.environ.get("DOWNLOAD_PREFIX", GeokubeAPIRequester.API_URL)
        )
        return requests
