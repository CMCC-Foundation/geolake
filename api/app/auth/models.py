"""The module contains models related to the authentication and authorization"""
from starlette.authentication import SimpleUser


<<<<<<< HEAD
class GeoLakeUser(SimpleUser):
=======
class DDSUser(SimpleUser):
>>>>>>> release_0.1.1
    """Immutable class containing information about the authenticated user"""

    def __init__(self, username: str) -> None:
        super().__init__(username=username)

    @property
    def id(self):
        return self.username

    def __eq__(self, other) -> bool:
<<<<<<< HEAD
        if not isinstance(other, GeoLakeUser):
=======
        if not isinstance(other, DDSUser):
>>>>>>> release_0.1.1
            return False
        if self.username == other.username:
            return True
        return False

    def __ne__(self, other):
        return self != other

    def __repr__(self):
<<<<<<< HEAD
        return f"<GeoLakeUser(username={self.username}>"
=======
        return f"<DDSUser(username={self.username}>"
>>>>>>> release_0.1.1

    def __delattr__(self, name):
        if getattr(self, name, None) is not None:
            raise AttributeError("The attribute '{name}' cannot be deleted!")
        super().__delattr__(name)

    def __setattr__(self, name, value):
        if getattr(self, name, None) is not None:
            raise AttributeError(
                "The attribute '{name}' cannot modified when not None!"
            )
        super().__setattr__(name, value)
