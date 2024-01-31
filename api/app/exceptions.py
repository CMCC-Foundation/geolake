<<<<<<< HEAD
"""Module with GeoLake exceptions definitions"""
=======
"""Module with DDS exceptions definitions"""
>>>>>>> release_0.1.1
from typing import Optional

from fastapi import HTTPException


<<<<<<< HEAD
class BaseGeoLakeException(BaseException):
    """Base class for GeoLake.api exceptions"""
=======
class BaseDDSException(BaseException):
    """Base class for DDS.api exceptions"""
>>>>>>> release_0.1.1

    msg: str = "Bad request"
    code: int = 400

    def wrap_around_http_exception(self) -> HTTPException:
        """Wrap an exception around `fastapi.HTTPExcetion`"""
        return HTTPException(
            status_code=self.code,
            detail=self.msg,
        )


<<<<<<< HEAD
class EmptyUserTokenError(BaseGeoLakeException):
=======
class EmptyUserTokenError(BaseDDSException):
>>>>>>> release_0.1.1
    """Raised if `User-Token` is empty"""

    msg: str = "User-Token cannot be empty!"


<<<<<<< HEAD
class ImproperUserTokenError(BaseGeoLakeException):
=======
class ImproperUserTokenError(BaseDDSException):
>>>>>>> release_0.1.1
    """Raised if `User-Token` format is wrong"""

    msg: str = (
        "The format of the User-Token is wrong. It should be be in the format"
        " <user_id (UUID v4)>:<api_key (string)>!"
    )


<<<<<<< HEAD
class NoEligibleProductInDatasetError(BaseGeoLakeException):
=======
class NoEligibleProductInDatasetError(BaseDDSException):
>>>>>>> release_0.1.1
    """No eligible products in the dataset Error"""

    msg: str = (
        "No eligible products for the dataset '{dataset_id}' for the user"
        " with roles '{user_roles_names}'"
    )

    def __init__(self, dataset_id: str, user_roles_names: list[str]) -> None:
        self.msg = self.msg.format(
            dataset_id=dataset_id, user_roles_names=user_roles_names
        )
        super().__init__(self.msg)


<<<<<<< HEAD
class MissingKeyInCatalogEntryError(BaseGeoLakeException):
=======
class MissingKeyInCatalogEntryError(BaseDDSException):
>>>>>>> release_0.1.1
    """Missing key in the catalog entry"""

    msg: str = (
        "There is missing '{key}' in the catalog for '{dataset}' dataset."
    )

    def __init__(self, key, dataset):
        self.msg = self.msg.format(key=key, dataset=dataset)
        super().__init__(self.msg)


<<<<<<< HEAD
class MaximumAllowedSizeExceededError(BaseGeoLakeException):
=======
class MaximumAllowedSizeExceededError(BaseDDSException):
>>>>>>> release_0.1.1
    """Estimated size is too big"""

    msg: str = (
        "Maximum allowed size for '{dataset_id}.{product_id}' is"
        " {allowed_size_gb:.2f} GB but the estimated size is"
        " {estimated_size_gb:.2f} GB"
    )

    def __init__(
        self, dataset_id, product_id, estimated_size_gb, allowed_size_gb
    ):
        self.msg = self.msg.format(
            dataset_id=dataset_id,
            product_id=product_id,
            allowed_size_gb=allowed_size_gb,
            estimated_size_gb=estimated_size_gb,
        )
        super().__init__(self.msg)


<<<<<<< HEAD
class RequestNotYetAccomplished(BaseGeoLakeException):
    """Raised if geolake request was not finished yet"""
=======
class RequestNotYetAccomplished(BaseDDSException):
    """Raised if dds request was not finished yet"""
>>>>>>> release_0.1.1

    msg: str = (
        "Request with id: {request_id} does not exist or it is not"
        " finished yet!"
    )

    def __init__(self, request_id):
        self.msg = self.msg.format(request_id=request_id)
        super().__init__(self.msg)


<<<<<<< HEAD
class RequestNotFound(BaseGeoLakeException):
=======
class RequestNotFound(BaseDDSException):
>>>>>>> release_0.1.1
    """If the given request could not be found"""

    msg: str = "Request with ID '{request_id}' was not found"

    def __init__(self, request_id: int) -> None:
        self.msg = self.msg.format(request_id=request_id)
        super().__init__(self.msg)


<<<<<<< HEAD
class RequestStatusNotDone(BaseGeoLakeException):
=======
class RequestStatusNotDone(BaseDDSException):
>>>>>>> release_0.1.1
    """Raised when the submitted request failed"""

    msg: str = (
        "Request with id: `{request_id}` does not have download. URI. Its"
        " status is: `{request_status}`!"
    )

    def __init__(self, request_id, request_status) -> None:
        self.msg = self.msg.format(
            request_id=request_id, request_status=request_status
        )
        super().__init__(self.msg)


<<<<<<< HEAD
class AuthorizationFailed(BaseGeoLakeException):
=======
class AuthorizationFailed(BaseDDSException):
>>>>>>> release_0.1.1
    """Raised when the user is not authorized for the given resource"""

    msg: str = "{user} is not authorized for the resource!"
    code: int = 403

    def __init__(self, user_id: Optional[str] = None):
        if user_id is None:
            self.msg = self.msg.format(user="User")
        else:
            self.msg = self.msg.format(user=f"User '{user_id}'")
        super().__init__(self.msg)


<<<<<<< HEAD
class AuthenticationFailed(BaseGeoLakeException):
=======
class AuthenticationFailed(BaseDDSException):
>>>>>>> release_0.1.1
    """Raised when the key of the provided user differs from the one s
    tored in the DB"""

    msg: str = "Authentication of the user '{user_id}' failed!"
    code: int = 401

    def __init__(self, user_id: str):
        self.msg = self.msg.format(user_id=user_id)
        super().__init__(self.msg)


<<<<<<< HEAD
class MissingDatasetError(BaseGeoLakeException):
=======
class MissingDatasetError(BaseDDSException):
>>>>>>> release_0.1.1
    """Raied if the queried dataset is not present in the catalog"""

    msg: str = "Dataset '{dataset_id}' does not exist in the catalog!"

    def __init__(self, dataset_id: str):
        self.msg = self.msg.format(dataset_id=dataset_id)
        super().__init__(self.msg)


<<<<<<< HEAD
class MissingProductError(BaseGeoLakeException):
=======
class MissingProductError(BaseDDSException):
>>>>>>> release_0.1.1
    """Raised if the requested product is not defined for the dataset"""

    msg: str = (
        "Product '{dataset_id}.{product_id}' does not exist in the catalog!"
    )

    def __init__(self, dataset_id: str, product_id: str):
        self.msg = self.msg.format(
            dataset_id=dataset_id, product_id=product_id
        )
        super().__init__(self.msg)


<<<<<<< HEAD
class EmptyDatasetError(BaseGeoLakeException):
=======
class EmptyDatasetError(BaseDDSException):
>>>>>>> release_0.1.1
    """The size of the requested dataset is zero"""

    msg: str = "The resulting dataset '{dataset_id}.{product_id}' is empty"

    def __init__(self, dataset_id, product_id):
        self.msg = self.msg.format(
            dataset_id=dataset_id,
            product_id=product_id,
        )
        super().__init__(self.msg)

<<<<<<< HEAD
class ProductRetrievingError(BaseGeoLakeException):
=======
class ProductRetrievingError(BaseDDSException):
>>>>>>> release_0.1.1
    """Retrieving of the product failed."""

    msg: str = "Retrieving of the product '{dataset_id}.{product_id}' failed with the status {status}"

    def __init__(self, dataset_id, product_id, status):
        self.msg = self.msg.format(
            dataset_id=dataset_id,
            product_id=product_id,
            status=status
        )
        super().__init__(self.msg)