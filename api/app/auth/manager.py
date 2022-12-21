"""Module with access/authentication functions"""
from inspect import signature
from functools import wraps
from typing import Optional

from ..api_logging import get_dds_logger
from ..auth import Context
from ..decorators_factory import assert_parameters_are_defined, bind_arguments
from .. import exceptions as exc

log = get_dds_logger(__name__)


def is_role_eligible_for_product(
    context: Context,
    product_role_name: Optional[str] = None,
    user_roles_names: Optional[list[str]] = None,
):
    """Check if given role is eligible for the product with the provided
    `product_role_name`.

    Parameters
    ----------
    product_role_name : str, optional, default=None
        The role which is eligible for the given product.
        If `None`, product_role_name is claimed to be public
    user_roles_names: list of str, optional, default=None
        A list of user roles names. If `None`, user_roles_names is claimed
        to be public

    Returns
    -------
    is_eligible : bool
        Flag which indicate if any role within the given `user_roles_names`
        is eligible for the product with `product_role_name`
    """
    log.debug(
        "verifying eligibility of the product role '%s' against roles '%s'",
        product_role_name,
        user_roles_names,
        extra={"rid": context.rid},
    )
    if product_role_name == "public" or product_role_name is None:
        return True
    if user_roles_names is None:
        # NOTE: it means, we consider the public profile
        return False
    if "admin" in user_roles_names:
        return True
    if product_role_name in user_roles_names:
        return True
    return False


def assert_is_role_eligible(
    context: Context,
    product_role_name: Optional[str] = None,
    user_roles_names: Optional[list[str]] = None,
):
    """Assert that user role is eligible for the product

    Parameters
    ----------
    product_role_name : str, optional, default=None
        The role which is eligible for the given product.
        If `None`, product_role_name is claimed to be public
    user_roles_names: list of str, optional, default=None
        A list of user roles names. If `None`, user_roles_names is claimed
        to be public

    Raises
    -------
    AuthorizationFailed
    """
    if not is_role_eligible_for_product(
        context=context,
        product_role_name=product_role_name,
        user_roles_names=user_roles_names,
    ):
        raise exc.AuthorizationFailed(user_id=context.user.id)


def assert_not_anonymous(func):
    """Decorator for convenient authentication management"""
    sig = signature(func)
    assert_parameters_are_defined(
        sig, required_parameters=[("context", Context)]
    )

    @wraps(func)
    def wrapper_sync(*args, **kwargs):
        args_dict = bind_arguments(sig, *args, **kwargs)
        context = args_dict["context"]
        if context.is_public:
            raise exc.AuthorizationFailed(user_id=None)
        return func(*args, **kwargs)

    return wrapper_sync
