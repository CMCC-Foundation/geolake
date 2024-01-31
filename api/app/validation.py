from datastore.datastore import Datastore
from utils.api_logging import get_dds_logger
from decorators_factory import assert_parameters_are_defined, bind_arguments
from functools import wraps
from inspect import signature
import exceptions as exc


log = get_dds_logger(__name__)


def assert_product_exists(func):
    """Decorator for convenient checking if product is defined in the catalog"""
    sig = signature(func)
    assert_parameters_are_defined(
        sig, required_parameters=[("dataset_id", str), ("product_id", str)]
    )

    @wraps(func)
    def assert_inner(*args, **kwargs):
        args_dict = bind_arguments(sig, *args, **kwargs)
        dataset_id = args_dict["dataset_id"]
        product_id = args_dict["product_id"]
        if dataset_id not in Datastore().dataset_list():
            raise exc.MissingDatasetError(dataset_id=dataset_id)
        elif (
            product_id is not None
            and product_id not in Datastore().product_list(dataset_id)
        ):
            raise exc.MissingProductError(
                dataset_id=dataset_id, product_id=product_id
            )
        return func(*args, **kwargs)

    return assert_inner
