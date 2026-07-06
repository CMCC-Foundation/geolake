import json
import logging
from enum import Enum

from geoquery.geoquery import GeoQuery
from geoquery.task import TaskList


class MessageType(Enum):
    QUERY = "query"
    WORKFLOW = "workflow"


class Message:
    _LOG = logging.getLogger("geokube.Message")

    request_id: str
    dataset_id: str = "<unknown>"
    product_id: str = "<unknown>"
    type: MessageType
    content: GeoQuery | TaskList

    def __init__(self, load: bytes) -> None:
        # Messages are framed as a JSON envelope (SEC-5). This is robust to any
        # content, unlike the previous separator-joined string which a payload
        # embedding the separator character could corrupt.
        try:
            data = json.loads(load)
        except (json.JSONDecodeError, TypeError, ValueError) as err:
            self._LOG.error("message is not valid JSON")
            raise ValueError("message is not a valid JSON envelope") from err
        if not isinstance(data, dict):
            raise ValueError("message envelope must be a JSON object")
        try:
            # The JSON envelope (SEC-5) preserves the numeric type of the DB
            # primary key, whereas the previous separator-joined string always
            # yielded a str. Downstream code builds download paths and filenames
            # from request_id (os.path.join / "_".join), so normalize to str
            # here. The DB layer coerces it back to the Integer PK on lookup.
            self.request_id = str(data["request_id"])
            msg_type = data["type"]
        except KeyError as err:
            raise ValueError(
                f"message envelope is missing required key: {err}"
            ) from err

        match MessageType(msg_type):
            case MessageType.QUERY:
                self._LOG.debug("processing content of `query` type")
                try:
                    self.dataset_id = data["dataset_id"]
                    self.product_id = data["product_id"]
                    content = data["content"]
                except KeyError as err:
                    raise ValueError(
                        f"query message is missing required key: {err}"
                    ) from err
                self.content: GeoQuery = GeoQuery.parse(content)
                self.type = MessageType.QUERY
            case MessageType.WORKFLOW:
                self._LOG.debug("processing content of `workflow` type")
                try:
                    content = data["content"]
                except KeyError as err:
                    raise ValueError(
                        f"workflow message is missing required key: {err}"
                    ) from err
                self.content: TaskList = TaskList.parse(content)
                self.dataset_id = self.content.dataset_id
                self.product_id = self.content.product_id
                self.type = MessageType.WORKFLOW
            case _:
                self._LOG.error("type `%s` is not supported", msg_type)
                raise ValueError(f"type `{msg_type}` is not supported!")
