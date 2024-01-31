import logging

from dbmanager.dbmanager import Request
from geodds_utils.queries import GeoQuery, TaskList

from intake_geokube.queries.geoquery import GeoQuery
from intake_geokube.queries.workflow import Workflow


class Message:
    _LOG = logging.getLogger("geokube.Message")

    request_id: int
    dataset_id: str = "<unknown>"
    product_id: str = "<unknown>"
    content: GeoQuery | Workflow

    def __init__(self, request: Request) -> None:
        self.request_id = request.request_id
        self._LOG.debug("processing workflow content")
        self.content: TaskList = TaskList.parse(request.query)
        self.dataset_id = self.content.dataset_id
        self.product_id = self.content.product_id
