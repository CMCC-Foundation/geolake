import os
import logging
from datetime import datetime

from dbmanager.dbmanager import DBManager, RequestStatus, Request

from geodds_utils.meta import LoggableMeta
from geodds_utils.messaging import Publisher
from geodds_utils.workflow import run_in_interval


class Broker(metaclass=LoggableMeta):
    _LOG = logging.getLogger("geokube.Broker")
    QUEUE_NAME: str = "execute"

    def __init__(self):
        self._LOG.debug(
            "setting up requests broker...", extra={"track_id": "n.a."}
        )
        self._request_limit: int = int(os.environ["RUNNING_REQUEST_LIMIT"])
        self._db = DBManager()
        self._LOG.debug(
            "request broker is ready. request limit set to %d",
            self._request_limit,
            extra={"track_id": "n.a."},
        )

    @property
    def _eligible_statuses(self) -> tuple[Request]:
        return (
            RequestStatus.QUEUED,
            RequestStatus.RUNNING,
        )

    @staticmethod
    def on_error_callback(err: Exception) -> None:
        Broker._LOG.error(
            "error occured during broker processing: %s",
            err,
            extra={"track_id": "n.a."},
        )
        raise err

    @staticmethod
    def pre() -> None:
        Broker._LOG.debug(
            "getting eligible requests for processing...",
            extra={"track_id": "n.a."},
        )

    @staticmethod
    def post() -> None:
        Broker._LOG.debug(
            "messages emitted sucesfully", extra={"track_id": "n.a."}
        )

    def is_request_schedulable(self, request: Request) -> bool:
        if (
            user_requests_nbr := len(
                self._db.get_request(
                    user_id=request.user_id, status=self._eligible_statuses
                )
            )
        ) < self._request_limit:
            return True
        self._LOG.debug(
            "user %s has too many (%d) requests in eligible status. maximum"
            " allowed number is %d",
            request.user_id,
            user_requests_nbr,
            self._request_limit,
            extra={"track_id": request.request_id},
        )
        return False

    def _process_single_schedulable_request(
        self, publisher: Publisher, request: Request
    ) -> None:
        timestamp_id: str = str(datetime.utcnow().isoformat())
        publisher.publish(str(request.request_id), timestamp_id)
        self._db.update_request(
            request_id=request.request_id,
            status=RequestStatus.QUEUED,
            lock=True,
        )

    @run_in_interval(
        every=int(os.environ["REQUEST_STATUS_CHECK_EVERY"]),
        retries=-1,
        pre=pre,
        post=post,
        on_error=on_error_callback,
    )
    def emit_permitted_messages_in_interval(self):
        self._LOG.debug(
            "obtaining pending request from the DB...",
            extra={"track_id": "n.a."},
        )
        pending_requests: list[Request] = self._db.get_request(
            status=RequestStatus.PENDING, sort=True
        )
        self._LOG.debug(
            "found %d pending requests",
            len(pending_requests),
            extra={"track_id": "n.a."},
        )
        publisher = Publisher(queue=self.QUEUE_NAME, use_venv_host=True)
        emitted_msg_counter: int = 0
        for request in pending_requests:
            if not self.is_request_schedulable(request):
                continue
            self._process_single_schedulable_request(
                publisher=publisher, request=request
            )
            emitted_msg_counter += 1
        self._LOG.debug(
            "%d requests published to the queue",
            emitted_msg_counter,
            extra={"track_id": "n.a."},
        )


if __name__ == "__main__":
    Broker().emit_permitted_messages_in_interval()
