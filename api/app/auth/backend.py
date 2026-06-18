"""The module contains authentication backend"""
import hmac
from uuid import UUID

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    UnauthenticatedUser,
)
from dbmanager.dbmanager import DBManager

import exceptions as exc
from auth.models import DDSUser
from auth import scopes


class DDSAuthenticationBackend(AuthenticationBackend):
    """Class managing authentication and authorization"""

    async def authenticate(self, conn):
        """Authenticate user based on `User-Token` header"""
        if "User-Token" in conn.headers:
            return self._manage_user_token_auth(conn.headers["User-Token"])
        return AuthCredentials([scopes.ANONYMOUS]), UnauthenticatedUser()

    def _manage_user_token_auth(self, user_token: str):
        try:
            user_id, api_key = self.get_authorization_scheme_param(user_token)
        except exc.BaseDDSException as err:
            # Malformed/empty token -> 400. Raised as DDSAuthenticationError so
            # the AuthenticationMiddleware routes it to `on_error` (a bare
            # HTTPException raised here would surface as 500).
            raise exc.DDSAuthenticationError(
                code=err.code, detail=err.msg
            ) from err
        user_dto = DBManager().get_user_details(user_id)
        if (
            user_dto is None
            or user_dto.api_key is None
            or not hmac.compare_digest(
                str(user_dto.api_key).encode("utf-8"), api_key.encode("utf-8")
            )
        ):
            # Unknown user or wrong API key -> 401. Both cases share the same
            # message so the response does not reveal whether the user exists.
            # `hmac.compare_digest` is constant-time to avoid leaking the key
            # via response timing.
            raise exc.DDSAuthenticationError(
                code=401,
                detail=f"Authentication of the user '{user_id}' failed!",
            )
        eligible_scopes = [scopes.AUTHENTICATED] + self._get_scopes_for_user(
            user_dto=user_dto
        )
        return AuthCredentials(eligible_scopes), DDSUser(username=user_id)

    def _get_scopes_for_user(self, user_dto) -> list[str]:
        if user_dto is None:
            return []
        eligible_scopes = []
        for role in user_dto.roles:
            if "admin" == role.role_name:
                eligible_scopes.append(scopes.ADMIN)
                continue
            # NOTE: Role-specific scopes
            # Maybe need some more logic
            eligible_scopes.append(role.role_name)
        return eligible_scopes

    def get_authorization_scheme_param(self, user_token: str):
        """Get `user_id` and `api_key` if authorization scheme is correct."""
        if user_token is None or user_token.strip() == "":
            raise exc.EmptyUserTokenError
        if ":" not in user_token:
            raise exc.ImproperUserTokenError
        user_id, api_key, *rest = user_token.split(":")
        if len(rest) > 0:
            raise exc.ImproperUserTokenError
        try:
            _ = UUID(user_id, version=4)
        except ValueError as err:
            raise exc.ImproperUserTokenError from err
        return (user_id, api_key)
