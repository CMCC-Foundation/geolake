"""The module contains authentication backend"""

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
            raise err.wrap_around_http_exception()
        user_dto = DBManager().get_user_details(user_id)
        eligible_scopes = [scopes.AUTHENTICATED] + self._get_scopes_for_user(
            user_dto=user_dto
        )
        if user_dto.api_key != api_key:
            raise exc.AuthenticationFailed(
                user_dto
            ).wrap_around_http_exception()
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
