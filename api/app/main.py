"""Main module with dekube-dds API endpoints defined"""
__version__ = "2.0"
import os
from uuid import uuid4
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from aioprometheus import Counter, Summary, timer, MetricsMiddleware
from aioprometheus.asgi.starlette import metrics

from geoquery.geoquery import GeoQuery

from .auth.context import ContextCreator
from .api_logging import get_dds_logger
from . import exceptions as exc
from .endpoint_handlers import (
    dataset_handler,
    file_handler,
    request_handler,
    user_handler,
)
from .endpoint_handlers.user import UserDTO
from .callbacks import all_onstartup_callbacks
from .encoders import extend_json_encoders

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
    root_path=os.environ.get("ENDPOINT_PREFIX", "/api"),
    on_startup=all_onstartup_callbacks,
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
    """Return current version of the DDS API"""
    return f"DDS API {__version__}"


@app.get("/datasets")
@timer(app.state.request_time, labels={"route": "GET /datasets"})
async def get_datasets(
    request: Request,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """List all products eligible for a user defined by user_token"""
    app.state.request.inc({"route": "GET /datasets"})
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return dataset_handler.get_datasets(context)
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/datasets/{dataset_id}/{product_id}")
@timer(
    app.state.request_time,
    labels={"route": "GET /datasets/{dataset_id}/{product_id}"},
)
async def get_product_details(
    request: Request,
    dataset_id: str,
    product_id: str,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Get details for the requested product if user is authorized"""
    app.state.request.inc({"route": "GET /datasets/{dataset_id}/{product_id}"})
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return dataset_handler.get_product_details(
            context,
            dataset_id=dataset_id,
            product_id=product_id,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/datasets/{dataset_id}/{product_id}/metadata")
@timer(
    app.state.request_time,
    labels={"route": "GET /datasets/{dataset_id}/{product_id}/metadata"},
)
async def get_metadata(
    request: Request,
    dataset_id: str,
    product_id: str,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Get metadata of the given product"""
    app.state.request.inc(
        {"route": "GET /datasets/{dataset_id}/{product_id}/metadata"}
    )
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return dataset_handler.get_metadata(
            context, dataset_id=dataset_id, product_id=product_id
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.post("/datasets/{dataset_id}/{product_id}/estimate")
@timer(
    app.state.request_time,
    labels={"route": "POST /datasets/{dataset_id}/{product_id}/estimate"},
)
async def estimate(
    request: Request,
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
    unit: str = None,
):
    """Estimate the resulting size of the query"""
    app.state.request.inc(
        {"route": "POST /datasets/{dataset_id}/{product_id}/estimate"}
    )
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return dataset_handler.estimate(
            context,
            dataset_id=dataset_id,
            product_id=product_id,
            query=query,
            unit=unit,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.post("/datasets/{dataset_id}/{product_id}/execute")
@timer(
    app.state.request_time,
    labels={"route": "POST /datasets/{dataset_id}/{product_id}/execute"},
)
async def query(
    request: Request,
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Schedule the job of data retrieve"""
    app.state.request.inc(
        {"route": "POST /datasets/{dataset_id}/{product_id}/execute"}
    )
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return dataset_handler.query(
            context,
            dataset_id=dataset_id,
            product_id=product_id,
            query=query,
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/requests")
@timer(app.state.request_time, labels={"route": "GET /requests"})
async def get_requests(
    request: Request,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Get all requests for the user"""
    app.state.request.inc({"route": "GET /requests"})
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return request_handler.get_requests(context)
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/requests/{request_id}/status")
@timer(
    app.state.request_time,
    labels={"route": "GET /requests/{request_id}/status"},
)
async def get_request_status(
    request: Request,
    request_id: int,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Get status of the request without authentication"""
    # NOTE: no auth required for checking status
    app.state.request.inc({"route": "GET /requests/{request_id}/status"})
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return request_handler.get_request_status(
            context, request_id=request_id
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/requests/{request_id}/size")
@timer(
    app.state.request_time, labels={"route": "GET /requests/{request_id}/size"}
)
async def get_request_resulting_size(
    request: Request,
    request_id: int,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Get size of the file being the result of the request"""
    app.state.request.inc({"route": "GET /requests/{request_id}/size"})
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return request_handler.get_request_resulting_size(
            context, request_id=request_id
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/requests/{request_id}/uri")
@timer(
    app.state.request_time, labels={"route": "GET /requests/{request_id}/uri"}
)
async def get_request_uri(
    request: Request,
    request_id: int,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Get download URI for the request"""
    app.state.request.inc({"route": "GET /requests/{request_id}/uri"})
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return request_handler.get_request_uri(context, request_id=request_id)
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err


@app.get("/download/{request_id}")
@timer(app.state.request_time, labels={"route": "GET /download/{request_id}"})
async def download_request_result(
    request: Request,
    request_id: int,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Download result of the request"""
    app.state.request.inc({"route": "GET /download/{request_id}"})
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return file_handler.download_request_result(
            context, request_id=request_id
        )
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=404, detail="File was not found!"
        ) from err


@app.post("/users/add")
@timer(app.state.request_time, labels={"route": "POST /users/add/"})
async def add_user(
    request: Request,
    user: UserDTO,
    dds_request_id: str = Header(str(uuid4()), convert_underscores=True),
    user_token: Optional[str] = Header(None, convert_underscores=True),
):
    """Add user to the database"""
    app.state.request.inc({"route": "POST /users/add/"})
    try:
        context = ContextCreator.new_context(
            request, rid=dds_request_id, user_token=user_token
        )
        return user_handler.add_user(context, user)
    except exc.BaseDDSException as err:
        raise err.wrap_around_http_exception() from err
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
