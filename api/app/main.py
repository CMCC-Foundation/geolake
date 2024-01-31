"""Main module with dekube-dds API endpoints defined"""

__version__ = "2.0"
import os
from typing import Optional

from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, status, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.authentication import requires

from aioprometheus import (
    Counter,
    Summary,
    timer,
    MetricsMiddleware,
)
from aioprometheus.asgi.starlette import metrics

from intake_geokube.queries.workflow import Workflow
from intake_geokube.queries.geoquery import GeoQuery

from utils.api_logging import get_dds_logger
import exceptions as exc
from endpoint_handlers import (
    dataset_handler,
    file_handler,
    request_handler,
)
from auth.backend import DDSAuthenticationBackend
from callbacks import all_onstartup_callbacks
from encoders import extend_json_encoders
from const import venv, tags
from auth import scopes


def map_to_geoquery(
    variables: list[str],
    format: str,
    bbox: (
        str | None
    ) = None,  # minx, miny, maxx, maxy (minlon, minlat, maxlon, maxlat)
    time: datetime | None = None,
    **format_kwargs,
) -> GeoQuery:

    bbox_ = [float(x) for x in bbox.split(",")]
    area = {
        "west": bbox_[0],
        "south": bbox_[1],
        "east": bbox_[2],
        "north": bbox_[3],
    }
    time_ = {
        "year": time.year,
        "month": time.month,
        "day": time.day,
        "hour": time.hour,
    }
    query = GeoQuery(
        variable=variables,
        time=time_,
        area=area,
        format_args=format_kwargs,
        format=format,
    )
    return query


logger = get_dds_logger(__name__)

# ======== JSON encoders extension ========= #
extend_json_encoders()

app = FastAPI(
    title="geokube-dds API",
    description="REST API for geokube-dds",
    version=__version__,
    contact={
        "name": "geokube Contributors",
        "email": "geokube@googlegroups.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    root_path=os.environ.get(venv.ENDPOINT_PREFIX, "/api"),
    on_startup=all_onstartup_callbacks,
)

# ======== Authentication backend ========= #
app.add_middleware(
    AuthenticationMiddleware, backend=DDSAuthenticationBackend()
)

# ======== CORS ========= #
cors_kwargs: dict[str, str | list[str]]
if venv.ALLOWED_CORS_ORIGINS_REGEX in os.environ:
    cors_kwargs = {
        "allow_origin_regex": os.environ[venv.ALLOWED_CORS_ORIGINS_REGEX]
    }
else:
    cors_kwargs = {"allow_origins": ["*"]}

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **cors_kwargs,
)


# ======== Prometheus metrics ========= #
app.add_middleware(MetricsMiddleware)
app.add_route("/metrics", metrics)

app.state.api_request_duration_seconds = Summary(
    "api_request_duration_seconds", "Requests duration"
)
app.state.api_http_requests_total = Counter(
    "api_http_requests_total", "Total number of requests"
)


# ======== Endpoints definitions ========= #
@app.get("/", tags=[tags.BASIC])
async def dds_info():
    """Return current version of the DDS API"""
    return f"DDS API {__version__}"


@app.get("/datasets", tags=[tags.DATASET])
@timer(
    app.state.api_request_duration_seconds, labels={"route": "GET /datasets"}
)
async def get_datasets(request: Request):
    """List all products eligible for a user defined by user_token"""
    app.state.api_http_requests_total.inc({"route": "GET /datasets"})
    try:
        return dataset_handler.get_datasets(
            user_roles_names=request.auth.scopes
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/datasets/{dataset_id}", tags=[tags.DATASET])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /datasets/{dataset_id}"},
)
async def get_first_product_details(
    request: Request,
    dataset_id: str,
):
    """Get details for the 1st product of the dataset"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /datasets/{dataset_id}"}
    )
    try:
        return dataset_handler.get_product_details(
            user_roles_names=request.auth.scopes,
            dataset_id=dataset_id,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/datasets/{dataset_id}/{product_id}", tags=[tags.DATASET])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /datasets/{dataset_id}/{product_id}"},
)
async def get_product_details(
    request: Request,
    dataset_id: str,
    product_id: str,
):
    """Get details for the requested product if user is authorized"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /datasets/{dataset_id}/{product_id}"}
    )
    try:
        return dataset_handler.get_product_details(
            user_roles_names=request.auth.scopes,
            dataset_id=dataset_id,
            product_id=product_id,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/datasets/{dataset_id}/{product_id}/map", tags=[tags.DATASET])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /datasets/{dataset_id}/{product_id}"},
)
async def get_map(
    request: Request,
    dataset_id: str,
    product_id: str,
    # OGC WMS parameters
    width: int,
    height: int,
    layers: str | None = None,
    format: str | None = "png",
    time: datetime | None = None,
    transparent: bool | None = "true",
    bgcolor: str | None = "FFFFFF",
    bbox: (
        str | None
    ) = None,  # minx, miny, maxx, maxy (minlon, minlat, maxlon, maxlat)
    crs: str | None = None,
    # OGC map parameters
    # subset: str | None = None,
    # subset_crs: str | None = Query(..., alias="subset-crs"),
    # bbox_crs: str | None = Query(..., alias="bbox-crs"),
):

    app.state.api_http_requests_total.inc(
        {"route": "GET /datasets/{dataset_id}/{product_id}/map"}
    )
    # query should be the OGC query
    # map OGC parameters to GeoQuery
    # variable: Optional[Union[str, List[str]]]
    # time: Optional[Union[Dict[str, str], Dict[str, List[str]]]]
    # area: Optional[Dict[str, float]]
    # location: Optional[Dict[str, Union[float, List[float]]]]
    # vertical: Optional[Union[float, List[float], Dict[str, float]]]
    # filters: Optional[Dict]
    # format: Optional[str]
    query = map_to_geoquery(
        variables=layers,
        bbox=bbox,
        time=time,
        format="png",
        width=width,
        height=height,
        transparent=transparent,
        bgcolor=bgcolor,
    )
    try:
        return dataset_handler.sync_query(
            user_id=request.user.id,
            dataset_id=dataset_id,
            product_id=product_id,
            query=query,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get(
    "/datasets/{dataset_id}/{product_id}/items/{feature_id}",
    tags=[tags.DATASET],
)
@timer(
    app.state.api_request_duration_seconds,
    labels={
        "route": "GET /datasets/{dataset_id}/{product_id}/items/{feature_id}"
    },
)
async def get_feature(
    request: Request,
    dataset_id: str,
    product_id: str,
    feature_id: str,
    # OGC feature parameters
    time: datetime | None = None,
    bbox: (
        str | None
    ) = None,  # minx, miny, maxx, maxy (minlon, minlat, maxlon, maxlat)
    crs: str | None = None,
    # OGC map parameters
    # subset: str | None = None,
    # subset_crs: str | None = Query(..., alias="subset-crs"),
    # bbox_crs: str | None = Query(..., alias="bbox-crs"),
):

    app.state.api_http_requests_total.inc(
        {"route": "GET /datasets/{dataset_id}/{product_id}/items/{feature_id}"}
    )
    # query should be the OGC query
    # feature OGC parameters to GeoQuery
    # variable: Optional[Union[str, List[str]]]
    # time: Optional[Union[Dict[str, str], Dict[str, List[str]]]]
    # area: Optional[Dict[str, float]]
    # location: Optional[Dict[str, Union[float, List[float]]]]
    # vertical: Optional[Union[float, List[float], Dict[str, float]]]
    # filters: Optional[Dict]
    # format: Optional[str]

    query = map_to_geoquery(
        variables=[feature_id], bbox=bbox, time=time, format="geojson"
    )
    try:
        return dataset_handler.sync_query(
            user_id=request.user.id,
            dataset_id=dataset_id,
            product_id=product_id,
            query=query,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/datasets/{dataset_id}/{product_id}/metadata", tags=[tags.DATASET])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /datasets/{dataset_id}/{product_id}/metadata"},
)
async def get_metadata(
    request: Request,
    dataset_id: str,
    product_id: str,
):
    """Get metadata of the given product"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /datasets/{dataset_id}/{product_id}/metadata"}
    )
    try:
        return dataset_handler.get_metadata(
            dataset_id=dataset_id, product_id=product_id
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.post("/datasets/{dataset_id}/{product_id}/estimate", tags=[tags.DATASET])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "POST /datasets/{dataset_id}/{product_id}/estimate"},
)
async def estimate(
    request: Request,
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
    unit: str = None,
):
    """Estimate the resulting size of the query"""
    app.state.api_http_requests_total.inc(
        {"route": "POST /datasets/{dataset_id}/{product_id}/estimate"}
    )
    try:
        return dataset_handler.estimate(
            dataset_id=dataset_id,
            product_id=product_id,
            query=query,
            unit=unit,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.post("/datasets/{dataset_id}/{product_id}/execute", tags=[tags.DATASET])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "POST /datasets/{dataset_id}/{product_id}/execute"},
)
@requires([scopes.AUTHENTICATED])
async def query(
    request: Request,
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
):
    """Schedule the job of data retrieve"""
    app.state.api_http_requests_total.inc(
        {"route": "POST /datasets/{dataset_id}/{product_id}/execute"}
    )
    try:
        return dataset_handler.async_query(
            user_id=request.user.id,
            dataset_id=dataset_id,
            product_id=product_id,
            query=query,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.post("/datasets/workflow", tags=[tags.DATASET])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "POST /datasets/workflow"},
)
@requires([scopes.AUTHENTICATED])
async def workflow(
    request: Request,
    tasks: Workflow,
):
    """Schedule the job of workflow processing"""
    app.state.api_http_requests_total.inc({"route": "POST /datasets/workflow"})
    try:
        return dataset_handler.run_workflow(
            user_id=request.user.id,
            workflow=tasks,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/requests", tags=[tags.REQUEST])
@timer(
    app.state.api_request_duration_seconds, labels={"route": "GET /requests"}
)
@requires([scopes.AUTHENTICATED])
async def get_requests(
    request: Request,
):
    """Get all requests for the user"""
    app.state.api_http_requests_total.inc({"route": "GET /requests"})
    try:
        return request_handler.get_requests(request.user.id)
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/requests/{request_id}/status", tags=[tags.REQUEST])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /requests/{request_id}/status"},
)
@requires([scopes.AUTHENTICATED])
async def get_request_status(
    request: Request,
    request_id: int,
):
    """Get status of the request without authentication"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /requests/{request_id}/status"}
    )
    try:
        return request_handler.get_request_status(
            user_id=request.user.id, request_id=request_id
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/requests/{request_id}/size", tags=[tags.REQUEST])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /requests/{request_id}/size"},
)
@requires([scopes.AUTHENTICATED])
async def get_request_resulting_size(
    request: Request,
    request_id: int,
):
    """Get size of the file being the result of the request"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /requests/{request_id}/size"}
    )
    try:
        return request_handler.get_request_resulting_size(
            request_id=request_id
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/requests/{request_id}/uri", tags=[tags.REQUEST])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /requests/{request_id}/uri"},
)
@requires([scopes.AUTHENTICATED])
async def get_request_uri(
    request: Request,
    request_id: int,
):
    """Get download URI for the request"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /requests/{request_id}/uri"}
    )
    try:
        return request_handler.get_request_uri(request_id=request_id)
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/download/{request_id}", tags=[tags.REQUEST])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /download/{request_id}"},
)
# @requires([scopes.AUTHENTICATED]) # TODO: mange download auth in the web component
async def download_request_result(
    request: Request,
    request_id: int,
):
    """Download result of the request"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /download/{request_id}"}
    )
    try:
        return file_handler.download_request_result(request_id=request_id)
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File was not found!"
        ) from err
