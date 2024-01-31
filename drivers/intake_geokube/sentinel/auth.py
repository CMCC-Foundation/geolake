"""Module with auth utils for accessing sentinel data."""

import os

import requests
from requests.auth import AuthBase


class SentinelAuth(AuthBase):  # pylint: disable=too-few-public-methods
    """Class ewith authentication for accessing sentinel data."""

    _SENTINEL_AUTH_URL: str = os.environ.get(
        "SENTINEL_AUTH_URL",
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
    )

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    @classmethod
    def _get_access_token(cls, username: str, password: str) -> str:
        data = {
            "client_id": "cdse-public",
            "username": username,
            "password": password,
            "grant_type": "password",
        }
        try:
            response = requests.post(
                cls._SENTINEL_AUTH_URL, data=data, timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(
                "Access token creation failed. Reponse from the server was:"
                f" {response.json()}"
            ) from e
        return response.json()["access_token"]

    def __call__(self, request):
        """Add authorization header."""
        token: str = self._get_access_token(self.username, self.password)
        request.headers["Authorization"] = f"Bearer {token}"
        return request
