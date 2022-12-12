"""Module containing utils for geokube-dds API accessing"""
from __future__ import annotations
import os
import logging
import requests

from .utils import UserCredentials, log_execution_time
from .meta import LoggableMeta
from .exceptions import GeokubeAPIRequestFailed
from .context import Context


class GeokubeAPIRequester(metaclass=LoggableMeta):
    """The class handling requests to geokube dds API"""

    _LOG = logging.getLogger("GeokubeAPIRequester")
    API_URL: str = None
    _IS_INIT: bool = False

    @classmethod
    def init(cls):
        """Initialize class with API URL"""
        cls.API_URL = os.environ.get("API_URL", "https://ddshub.cmcc.it/api")
        cls._LOG.info(
            "'API_URL' environment variable collected: %s", cls.API_URL
        )
        cls._IS_INIT = True

    @staticmethod
    def _get_http_header_from_user_credentials(
        user_credentials: UserCredentials | None = None,
    ):
        if user_credentials is not None and user_credentials.id is not None:
            return {
                "User-Token": (
                    f"{user_credentials.id}:{user_credentials.user_token}"
                )
            }
        return {}

    @classmethod
    def _prepare_headers(cls, context: Context):
        headers = {
            "Content-Type": "application/json",
            "DDS-Request-Id": str(context.rid),
        }
        headers.update(
            GeokubeAPIRequester._get_http_header_from_user_credentials(
                context.user
            )
        )
        return headers

    @classmethod
    @log_execution_time(_LOG)
    def post(cls, url: str, data: str, context: Context):
        """
        Send POST request to geokube-dds API

        Parameters
        ----------
        url : str
            Path to which the query should be send. It is created as
            f"{GeokubeAPIRequester.API_URL{url}"
        data : str
            JSON payload of the request
        context : Context
            Context of the http request

        Returns
        -------
        response : str
            Response from geokube-dds API

        Raises
        -------
        GeokubeAPIRequestFailed
            If request failed due to any reason
        """
        assert cls._IS_INIT, "GeokubeAPIRequester was not initialized!"
        target_url = f"{cls.API_URL}{url}"
        headers = cls._prepare_headers(context)
        cls._LOG.debug("sending POST request to %s", target_url)
        cls._LOG.debug("payload of the POST request: %s", data)
        response = requests.post(
            target_url,
            data=data,
            headers=headers,
            timeout=int(os.environ.get("API_TIMEOUT", 20)),
        )
        if response.status_code != 200:
            raise GeokubeAPIRequestFailed(
                response.json().get(
                    "detail", "Request to geokube-dds API failed!"
                )
            )
        if "application/json" in response.headers.get("Content-Type", ""):
            return response.json()
        return response.text()

    @classmethod
    @log_execution_time(_LOG)
    def get(
        cls,
        url: str,
        context: Context,
        timeout: int = 10,
    ):
        """
        Send GET request to geokube-dds API

        Parameters
        ----------
        url : str
            Path to which the query should be send. It is created as
            f"{GeokubeAPIRequester.API_URL}{url}"
        context : Context
            Context of the http request
        timeout : int, default=10
            Request timout in seconds

        Returns
        -------
        response : str
            Response from geokube-dds API

        Raises
        -------
        GeokubeAPIRequestFailed
            If request failed due to any reason
        """
        assert cls._IS_INIT, "GeokubeAPIRequester was not initialized!"
        target_url = f"{cls.API_URL}{url}"
        headers = cls._prepare_headers(context)
        cls._LOG.debug("sending GET request to %s", target_url)
        response = requests.get(
            target_url,
            headers=headers,
            timeout=int(os.environ.get("API_TIMEOUT", timeout)),
        )
        if response.status_code != 200:
            cls._LOG.info(
                "request to geokube-dds API failed due to: %s", response.text
            )
            raise GeokubeAPIRequestFailed(
                response.json().get(
                    "detail", "Request to geokube-dds API failed!"
                )
            )
        return response.json()
