"""Main module with geolake API endpoints defined"""
__version__ = "0.1.0"
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
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

from geoquery.geoquery import GeoQuery
from geoquery.task import TaskList

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

logger = get_dds_logger(__name__)

# ======== JSON encoders extension ========= #
extend_json_encoders()

app = FastAPI(
    title="geolake API",
    description="REST API for geolake",
    version=__version__,
    contact={
        "name": "geolake Contributors",
        "email": "geolake@googlegroups.com",
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
async def geolake_info():
    """Return current version of the geolake API"""
    return f"geolake API {__version__}"


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
        return dataset_handler.query(
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
    tasks: TaskList,
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

@app.get("/download/{request_id}/{filename}", tags=[tags.REQUEST])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /download/{request_id}/{filename}"},
)
# @requires([scopes.AUTHENTICATED]) # TODO: mange download auth in the web component
async def download_request_result(
    request: Request,
    request_id: int,
    filename: str,
):
    """Download result of the request"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /download/{request_id}/{filename}"}
    )
    try:
        return file_handler.download_request_result(request_id=request_id, filename=filename)
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File was not found!"
        ) from err

@app.get("/download/{request_id}/{filename}/{subfile}", tags=[tags.REQUEST])
@timer(
    app.state.api_request_duration_seconds,
    labels={"route": "GET /download/{request_id}/{filename}/{subfile}"},
)
# @requires([scopes.AUTHENTICATED])
async def download_request_result(
    request: Request,
    request_id: int,
    filename: str,
    subfile: str,
):
    """Download result of the request"""
    app.state.api_http_requests_total.inc(
        {"route": "GET /download/{request_id}/{filename}/{subfile}"}
    )
    try:
        return file_handler.download_request_result(request_id=request_id, filename=f'{filename}/{subfile}')
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File was not found!"
        ) from err