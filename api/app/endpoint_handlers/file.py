"""Module with functions to handle file related endpoints"""
import io
import os
import zipfile
from pathlib import Path
from zipfile import ZipFile

from fastapi.responses import FileResponse


from dbmanager.dbmanager import DBManager, RequestStatus
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

from utils.api_logging import get_dds_logger
from utils.metrics import log_execution_time
import exceptions as exc
from security import safe_join

log = get_dds_logger(__name__)


@log_execution_time(log)
def download_request_result(
    request_id: int, user_id: str = None, filename: str = None
):
    """Realize the logic for the endpoint:

    `GET /download/{request_id}`

    Get location path of the file being the result of
    the request with `request_id`.

    Parameters
    ----------
    request_id : int
        ID of the request
    user_id : str
        ID of the user owning the request

    Returns
    -------
    path : str
        The location of the resulting file

    Raises
    -------
    RequestNotYetAccomplished
        If dds request was not yet finished
    AuthorizationFailed
        If the request does not belong to the user
    FileNotFoundError
        If file was not found
    """
    log.debug(
        "preparing downloads for request id: %s",
        request_id,
    )
    # Ownership is enforced at the datastore layer (SEC-10/SEC-11): a request
    # that does not belong to `user_id` raises PermissionError -> 403, a missing
    # one raises IndexError -> RequestNotFound.
    try:
        (
            request_status,
            _,
        ) = DBManager().get_request_status_and_reason(
            request_id=request_id, user_id=user_id
        )
    except IndexError as err:
        log.error("request with id: '%s' was not found!", request_id)
        raise exc.RequestNotFound(request_id=request_id) from err
    except PermissionError as err:
        log.warning(
            "user '%s' attempted to download request '%s' they do not own",
            user_id,
            request_id,
        )
        raise exc.AuthorizationFailed(user_id=user_id) from err
    if request_status is not RequestStatus.DONE:
        log.debug(
            "request with id: '%s' does not exist or it is not finished yet!",
            request_id,
        )
        raise exc.RequestNotYetAccomplished(request_id=request_id)
    download_details = DBManager().get_download_details_for_request_id(
        request_id=request_id, user_id=user_id
    )
    if not os.path.exists(download_details.location_path):
        log.error(
            "file '%s' does not exists!",
            download_details.location_path,
        )
        raise FileNotFoundError

    if download_details.location_path.endswith(".zarr"):
        log.info("Zarr detected")
        if not filename:
            raise exc.MalformedQueryParameterError(
                "A filename is required to download from a zarr result"
            )
        # Client-controlled `filename`/`subfile` must be contained within the
        # result directory; `_safe_join` blocks traversal and the basename used
        # for the Content-Disposition header prevents header injection (SEC-1/17).
        safe_path = safe_join(download_details.location_path, filename)
        return FileResponse(
            path=safe_path,
            filename=os.path.basename(safe_path),
        )
    else:
        return FileResponse(
            path=download_details.location_path,
            filename=download_details.location_path.split(os.sep)[-1],
        )
