"""Modules realizing logic for dataset-related endpoints"""

import json
from typing import Optional

from fastapi.responses import FileResponse

from geodds_utils.units import make_bytes_readable_dict
from geodds_utils.workflow import log_execution_time

from dbmanager.dbmanager import DBManager, RequestStatus
from intake_geokube.queries.geoquery import GeoQuery, Workflow
from intake_geokube.queries.workflow import Workflow
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

PENDING_QUEUE: str = "pending"


def convert_to_workflow(
    dataset_id: str, product_id: str, geoquery: GeoQuery
) -> Workflow:
    raw_task = {
        "id": "geoquery",
        "op": "subset",
        "use": [],
        "args": {
            "dataset_id": dataset_id,
            "product_id": product_id,
            "query": geoquery.dict(),
        },
    }
    return TaskList.parse([raw_task])


def _is_etimate_enabled(dataset_id, product_id):
    if dataset_id in ("sentinel-2",):
        return False
    return True


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
    if _is_etimate_enabled(dataset_id, product_id):
        estimated_size = estimate(dataset_id, product_id, query, "GB").get(
            "value"
        )
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

    request_id = DBManager().create_request(
        user_id=user_id,
        dataset=dataset_id,
        product=product_id,
        query=convert_to_workflow(dataset_id, product_id, query).json(),
        status=RequestStatus.PENDING,
    )
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

    request_id = async_query(user_id, dataset_id, product_id, query)
    status, _ = DBManager().get_request_status_and_reason(request_id)
    log.debug("sync query: status: %s", status)
    while status in (
        RequestStatus.RUNNING,
        RequestStatus.QUEUED,
        RequestStatus.PENDING,
    ):
        time.sleep(1)
        status, _ = DBManager().get_request_status_and_reason(request_id)
        log.debug("sync query: status: %s", status)

    if status is RequestStatus.DONE:
        download_details = DBManager().get_download_details_for_request_id(
            request_id
        )
        return FileResponse(
            path=download_details.location_path,
            filename=download_details.location_path.split(os.sep)[-1],
        )
    raise exc.ProductRetrievingError(
        dataset_id=dataset_id, product_id=product_id, status=status.name
    )


@log_execution_time(log)
def run_workflow(
    user_id: str,
    workflow: Workflow,
):
    """Realize the logic for the endpoint:

    `POST /datasets/workflow`

    Schedule the workflow and return the ID of the request.

    Parameters
    ----------
    user_id : str
        ID of the user executing the query
    workflow : Workflow
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

    request_id = DBManager().create_request(
        user_id=user_id,
        dataset=workflow.dataset_id,
        product=workflow.product_id,
        query=workflow.json(),
        status=RequestStatus.PENDING,
    )
    return request_id
