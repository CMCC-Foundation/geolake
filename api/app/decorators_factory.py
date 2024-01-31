"""Modules with utils for creating decorators"""

from inspect import Signature


def assert_parameters_are_defined(
    sig: Signature, required_parameters: list[tuple]
):
    """Assert the given callable signature has parameters with
    names and types indicated by `required_parameters` argument.

    Parameters
    ----------
    sig : Signature
        A signature object of a callable
    required_parameters : list of tuples
        List of two-element tuples containing a name and a type
        of the parameter, e.g. [("dataset_id", str)]

    Raises
    ------
    TypeError
        If a required parameter is not defined or is of wrong type
    """
    for param_name, param_type in required_parameters:
        if param_name not in sig.parameters:
            raise TypeError(
                f"The parameter '{param_name}' annotated with the type"
                f" '{param_type}' must be defined for the callable decorated"
                " with 'authenticate_user' decorator"
            )


def bind_arguments(sig: Signature, *args, **kwargs):
    """Bind arguments to the signature"""
    args_bind = sig.bind_partial(*args, **kwargs)
    args_bind.apply_defaults()
    return args_bind.arguments
