"""Modules with functions realizing logic for requests-related endpoints"""
from dbmanager.dbmanager import DBManager

from utils.api_logging import get_dds_logger
from utils.metrics import log_execution_time
import exceptions as exc

log = get_dds_logger(__name__)


@log_execution_time(log)
def get_requests(user_id: str):
    """Realize the logic for the endpoint:

    `GET /requests`

    Get details of all requests for the user.

    Parameters
    ----------
    user_id : str
        ID of the user for whom requests are taken

    Returns
    -------
    requests : list
        List of all requests done by the user
    """
    return DBManager().get_requests_for_user_id(user_id=user_id)


@log_execution_time(log)
def get_request_status(user_id: str, request_id: int):
    """Realize the logic for the endpoint:

    `GET /requests/{request_id}/status`

    Get request status and the reason of the eventual fail.
    The second item is `None`, it status is other than failed.

    Parameters
    ----------
    user_id : str
        ID of the user whose request's status is about to be checed
    request_id : int
        ID of the request

    Returns
    -------
    status : tuple
        Tuple of status and fail reason.
    """
    # NOTE: maybe verification should be added if user checks only him\her requests
    try:
        status, reason = DBManager().get_request_status_and_reason(request_id)
    except IndexError as err:
        log.error(
            "request with id: '%s' was not found!",
            request_id,
        )
        raise exc.RequestNotFound(request_id=request_id) from err
    return {"status": status.name, "fail_reason": reason}


@log_execution_time(log)
def get_request_resulting_size(request_id: int):
    """Realize the logic for the endpoint:

    `GET /requests/{request_id}/size`

    Get size of the file being the result of the request with `request_id`

    Parameters
    ----------
    request_id : int
        ID of the request

    Returns
    -------
    size : int
        Size in bytes

    Raises
    -------
    RequestNotFound
        If the request was not found
    """
    if request := DBManager().get_request_details(request_id):
        size = request.download.size_bytes
        if not size or size == 0:
            raise exc.EmptyDatasetError(dataset_id=request.dataset, 
                                        product_id=request.product)
        return size
    log.info(
        "request with id '%s' could not be found",
        request_id,
    )
    raise exc.RequestNotFound(request_id=request_id)


@log_execution_time(log)
def get_request_uri(request_id: int):
    """
    Realize the logic for the endpoint:

    `GET /requests/{request_id}/uri`

    Get URI for the request.

    Parameters
    ----------
    request_id : int
        ID of the request

    Returns
    -------
    uri : str
        URI for the download associated with the given request
    """
    try:
        download_details = DBManager().get_download_details_for_request_id(
            request_id
        )
    except IndexError as err:
        log.error(
            "request with id: '%s' was not found!",
            request_id,
        )
        raise exc.RequestNotFound(request_id=request_id) from err
    if download_details is None:
        (
            request_status,
            _,
        ) = DBManager().get_request_status_and_reason(request_id)
        log.info(
            "download URI not found for request id: '%s'."
            " Request status is '%s'",
            request_id,
            request_status,
        )
        raise exc.RequestStatusNotDone(
            request_id=request_id, request_status=request_status
        )
    return download_details.download_uri
