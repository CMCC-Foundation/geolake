"""Modules realizing logic for dataset-related endpoints"""
import os
import json
import pika
from typing import Optional

from fastapi.responses import FileResponse

from dbmanager.dbmanager import DBManager, RequestStatus
from geoquery.geoquery import GeoQuery
from geoquery.capabilities import DatasetCapabilities
from geoquery.task import TaskList
from datastore.datastore import Datastore, DEFAULT_MAX_REQUEST_SIZE_GB
from datastore import exception as datastore_exception

from utils.metrics import log_execution_time
from utils.api_logging import get_dds_logger
from auth.manager import (
    is_role_eligible_for_product,
)
import exceptions as exc
from api_utils import make_bytes_readable_dict
from validation import assert_product_exists

from . import request

log = get_dds_logger(__name__)
data_store = Datastore()


def _is_etimate_enabled(dataset_id, product_id):
    if dataset_id in ("sentinel-2",):
        return False
    return True


def _enforce_capabilities(
    dataset_id: str, product_id: str, query: GeoQuery
) -> None:
    """Reject a query that uses operations the product does not allow.

    Reads the product's catalog `capabilities` and raises
    `OperationNotSupportedError` (HTTP 400) on any violation. A product without
    a `capabilities` block is fully permissive (historical behavior).
    """
    capabilities = DatasetCapabilities.from_metadata(
        data_store.product_metadata(dataset_id, product_id)
    )
    violations = capabilities.check(query)
    if violations:
        raise exc.OperationNotSupportedError(
            dataset_id=dataset_id,
            product_id=product_id,
            violations=violations,
        )


@log_execution_time(log)
def get_datasets(user_roles_names: list[str]) -> list[dict]:
    """Realize the logic for the endpoint:

    `GET /datasets`

    Get datasets names, their metadata and products names (if eligible for a user).
    If no eligible products are found for a dataset, it is not included.

    Parameters
    ----------
    user_roles_names : list of str
        List of user's roles

    Returns
    -------
    datasets : list of dict
        A list of dictionaries with datasets information (including metadata and
        eligible products lists)

    Raises
    -------
    MissingKeyInCatalogEntryError
        If the dataset catalog entry does not contain the required key
    """
    log.debug(
        "getting all eligible products for datasets...",
    )
    datasets = []
    for dataset_id in data_store.dataset_list():
        log.debug(
            "getting info and eligible products for `%s`",
            dataset_id,
        )
        dataset_info = data_store.dataset_info(dataset_id=dataset_id)
        try:
            eligible_prods = {
                prod_name: prod_info
                for prod_name, prod_info in dataset_info["products"].items()
                if is_role_eligible_for_product(
                    product_role_name=prod_info.get("role"),
                    user_roles_names=user_roles_names,
                )
                # Hide products whose metadata cache has not been built yet
                # (metadata_caching=True + CacheNotExist); metadata_caching=False
                # products (e.g. native zarr) read directly and stay visible.
                and data_store.is_product_available(dataset_id, prod_name)
            }
        except KeyError as err:
            log.error(
                "dataset `%s` does not have products defined",
                dataset_id,
                exc_info=True,
            )
            raise exc.MissingKeyInCatalogEntryError(
                key="products", dataset=dataset_id
            ) from err
        else:
            if len(eligible_prods) == 0:
                log.debug(
                    "no eligible products for dataset `%s` for the role `%s`."
                    " dataset skipped",
                    dataset_id,
                    user_roles_names,
                )
            else:
                dataset_info["products"] = eligible_prods
                datasets.append(dataset_info)
    return datasets


@log_execution_time(log)
@assert_product_exists
def get_product_details(
    user_roles_names: list[str],
    dataset_id: str,
    product_id: Optional[str] = None,
) -> dict:
    """Realize the logic for the endpoint:

    `GET /datasets/{dataset_id}/{product_id}`

    Get details for the given product indicated by `dataset_id`
    and `product_id` arguments.

    Parameters
    ----------
    user_roles_names : list of str
        List of user's roles
    dataset_id : str
        ID of the dataset
    product_id : optional, str
        ID of the product. If `None` the 1st product will be considered

    Returns
    -------
    details : dict
        Details for the given product

    Raises
    -------
    AuthorizationFailed
        If user is not authorized for the resources
    """
    log.debug(
        "getting details for eligible products of `%s`",
        dataset_id,
    )
    try:
        if product_id:
            return data_store.product_details(
                dataset_id=dataset_id,
                product_id=product_id,
                role=user_roles_names,
                use_cache=True,
            )
        else:
            return data_store.first_eligible_product_details(
                dataset_id=dataset_id, role=user_roles_names, use_cache=True
            )
    except datastore_exception.UnauthorizedError as err:
        raise exc.AuthorizationFailed from err


@log_execution_time(log)
@assert_product_exists
def get_metadata(dataset_id: str, product_id: str):
    """Realize the logic for the endpoint:

    `GET /datasets/{dataset_id}/{product_id}/metadata`

    Get metadata for the product.

    Parameters
    ----------
    dataset_id : str
        ID of the dataset
    product_id : str
        ID of the product
    """
    log.debug(
        "getting metadata for '{dataset_id}.{product_id}'",
    )
    return data_store.product_metadata(dataset_id, product_id)


@log_execution_time(log)
@assert_product_exists
def estimate(
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
    unit: Optional[str] = None,
    enforce_capabilities: bool = True,
):
    """Realize the logic for the nedpoint:

    `POST /datasets/{dataset_id}/{product_id}/estimate`

    Estimate the size of the resulting data.
    No authentication is needed for estimation query.

    Parameters
    ----------
    dataset_id : str
        ID of the dataset
    product_id : str
        ID of the product
    query : GeoQuery
        Query to perform
    unit : str
        One of unit [bytes, kB, MB, GB] to present the result. If `None`,
        unit will be inferred.
    enforce_capabilities : bool, optional, default=True
        Reject the query if it uses an operation the product does not allow.
        Set to `False` when the caller has already enforced capabilities (e.g.
        `async_query`) or for the OGC sync path that injects internal queries.

    Returns
    -------
    size_details : dict
        Estimated size of  the query in the form:
        ```python
        {
            "value": val,
            "units": units
        }
        ```
    """
    if enforce_capabilities:
        _enforce_capabilities(dataset_id, product_id, query)
    query_bytes_estimation = data_store.estimate(dataset_id, product_id, query)
    return make_bytes_readable_dict(
        size_bytes=query_bytes_estimation, units=unit
    )


@log_execution_time(log)
@assert_product_exists
def async_query(
    user_id: str,
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
    enforce_capabilities: bool = True,
):
    """Realize the logic for the endpoint:

    `POST /datasets/{dataset_id}/{product_id}/execute`

    Query the data and return the ID of the request.

    Parameters
    ----------
    user_id : str
        ID of the user executing the query
    dataset_id : str
        ID of the dataset
    product_id : str
        ID of the product
    query : GeoQuery
        Query to perform
    enforce_capabilities : bool, optional, default=True
        Reject the query if it uses an operation the product does not allow.
        The OGC sync path (`sync_query`) passes `False` because it injects
        internal queries (e.g. `format=png`) that are not user-facing.

    Returns
    -------
    request_id : int
        ID of the request

    Raises
    -------
    MaximumAllowedSizeExceededError
        if the allowed size is below the estimated one
    EmptyDatasetError
        if estimated size is zero

    """
    log.debug("geoquery: %s", query)
    # Enforce *before* the estimate gate so products with estimation disabled
    # (see `_is_etimate_enabled`) are still subject to capability checks.
    if enforce_capabilities:
        _enforce_capabilities(dataset_id, product_id, query)
    if _is_etimate_enabled(dataset_id, product_id):
        estimated_size = estimate(
            dataset_id, product_id, query, "GB", enforce_capabilities=False
        ).get("value")
        allowed_size = data_store.product_metadata(dataset_id, product_id).get(
            "maximum_query_size_gb", DEFAULT_MAX_REQUEST_SIZE_GB
        )
        if estimated_size > allowed_size:
            raise exc.MaximumAllowedSizeExceededError(
                dataset_id=dataset_id,
                product_id=product_id,
                estimated_size_gb=estimated_size,
                allowed_size_gb=allowed_size,
            )
        if estimated_size == 0.0:
            raise exc.EmptyDatasetError(
                dataset_id=dataset_id, product_id=product_id
            )
    broker_conn = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.getenv("BROKER_SERVICE_HOST", "broker")
        )
    )
    broker_channel = broker_conn.channel()

    request_id = DBManager().create_request(
        user_id=user_id,
        dataset=dataset_id,
        product=product_id,
        query=query.original_query_json(),
    )

    # Frame the broker message as a JSON envelope (SEC-5). This is robust to
    # any content (the previous separator-joined string could be corrupted by
    # a payload embedding the separator character).
    message = json.dumps(
        {
            "request_id": request_id,
            "type": "query",
            "dataset_id": dataset_id,
            "product_id": product_id,
            "content": query.model_dump_json(),
        }
    )

    broker_channel.basic_publish(
        exchange="",
        routing_key="query_queue",
        body=message,
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        ),
    )
    broker_conn.close()
    return request_id

@log_execution_time(log)
@assert_product_exists
def sync_query(
    user_id: str,
    dataset_id: str,
    product_id: str,
    query: GeoQuery,
):
    """Realize the logic for the endpoint:

    `POST /datasets/{dataset_id}/{product_id}/execute`

    Query the data and return the result of the request.

    Parameters
    ----------
    user_id : str
        ID of the user executing the query
    dataset_id : str
        ID of the dataset
    product_id : str
        ID of the product
    query : GeoQuery
        Query to perform

    Returns
    -------
    request_id : int
        ID of the request

    Raises
    -------
    MaximumAllowedSizeExceededError
        if the allowed size is below the estimated one
    EmptyDatasetError
        if estimated size is zero

    """
    
    import time
    # OGC map/feature endpoints route here with internally-built queries
    # (e.g. `format=png`/`geojson`, bbox-derived `area`). They intentionally
    # bypass capability enforcement, which gates the user-facing query path.
    request_id = async_query(
        user_id, dataset_id, product_id, query, enforce_capabilities=False
    )
    status, _ = DBManager().get_request_status_and_reason(
        request_id, user_id=user_id
    )
    log.debug("sync query: status: %s", status)
    while status in (RequestStatus.RUNNING, RequestStatus.QUEUED,
                     RequestStatus.PENDING):
        time.sleep(1)
        status, _ = DBManager().get_request_status_and_reason(
            request_id, user_id=user_id
        )
        log.debug("sync query: status: %s", status)

    if status is RequestStatus.DONE:
        download_details = DBManager().get_download_details_for_request_id(
                request_id, user_id=user_id
        )
        return FileResponse(
            path=download_details.location_path,
            filename=download_details.location_path.split(os.sep)[-1],
        )
    raise exc.ProductRetrievingError(
        dataset_id=dataset_id, 
        product_id=product_id,
        status=status.name)


@log_execution_time(log)
def run_workflow(
    user_id: str,
    workflow: TaskList,
):
    """Realize the logic for the endpoint:

    `POST /datasets/workflow`

    Schedule the workflow and return the ID of the request.

    Parameters
    ----------
    user_id : str
        ID of the user executing the query
    workflow : TaskList
        Workflow to perform

    Returns
    -------
    request_id : int
        ID of the request

    Raises
    -------
    MaximumAllowedSizeExceededError
        if the allowed size is below the estimated one
    EmptyDatasetError
        if estimated size is zero

    """
    log.debug("geoquery: %s", workflow)
    broker_conn = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.getenv("BROKER_SERVICE_HOST", "broker")
        )
    )
    broker_channel = broker_conn.channel()
    serialized_workflow = workflow.model_dump_json()

    request_id = DBManager().create_request(
        user_id=user_id,
        dataset=workflow.dataset_id,
        product=workflow.product_id,
        query=serialized_workflow,
    )

    # Frame the broker message as a JSON envelope (SEC-5).
    message = json.dumps(
        {
            "request_id": request_id,
            "type": "workflow",
            "content": serialized_workflow,
        }
    )

    broker_channel.basic_publish(
        exchange="",
        routing_key="query_queue",
        body=message,
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        ),
    )
    broker_conn.close()
    return request_id
