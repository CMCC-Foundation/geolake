"""Utils module."""

import os

import requests


def create_zip_from_response(response: requests.Response, target: str) -> None:
    """Create ZIP archive based on the content in streamable response.

    Parameters
    ----------
    response : requests.Response
        Response whose contant is streamable (`stream=True`)
    target : str
        Target path containing name and .zip extension

    Raises
    ------
    ValueError
        if `Content-Type` header is missing
    TypeError
        if type supplied by `Content-Type` is other than `zip`
    RuntimError
        if size provided by `Content-Length` header differs from the size
        of the downloaded file
    """
    content_type = response.headers.get("Content-Type")
    if not content_type:
        raise ValueError("`Content-Type` mandatory header is missing")
    format_ = content_type.split("/")[-1]
    _, ext = os.path.splitext(target)
    if format_ != "zip":
        raise TypeError(
            f"provided content type {format_} is not allowed. expected 'zip'"
            " format"
        )
    assert ext[1:] == "zip", "expected target with '.zip' extension"

    expected_length = int(response.headers["Content-Length"])
    total_bytes = 0
    with open(target, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                total_bytes += len(chunk)
    if expected_length != total_bytes:
        raise RuntimeError(
            "downloaded file is not complete in spite of download finished"
            " successfully"
        )
