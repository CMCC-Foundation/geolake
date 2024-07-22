import os
import time
import datetime
import pika
import logging
import asyncio
import threading, functools
from zipfile import ZipFile

import numpy as np
from dask.distributed import Client, LocalCluster, Nanny, Status
from dask.delayed import Delayed
from geokube.core.datacube import DataCube
from geokube.core.dataset import Dataset
from geokube.core.field import Field

from datastore.datastore import Datastore
from workflow import Workflow
from geoquery.geoquery import GeoQuery
from dbmanager.dbmanager import DBManager, RequestStatus

from meta import LoggableMeta
from messaging import Message, MessageType

_BASE_DOWNLOAD_PATH = "/downloads"


def get_file_name_for_climate_downscaled(kube: DataCube, message: Message):
    query: GeoQuery = GeoQuery.parse(message.content)
    is_time_range = False
    if query.time:
        is_time_range = "start" in query.time or "stop" in query.time
    var_names = list(kube.fields.keys())
    if len(kube) == 1:
        if is_time_range:
            FILENAME_TEMPLATE = "{ncvar_name}_VHR-PRO_IT2km_CMCC-CM_{product_id}_CCLM5-0-9_1hr_{start_date}_{end_date}_{request_id}"
            ncvar_name = kube.fields[var_names[0]].ncvar
            return FILENAME_TEMPLATE.format(
                product_id=message.product_id,
                request_id=message.request_id,
                ncvar_name=ncvar_name,
                start_date=np.datetime_as_string(
                    kube.time.values[0], unit="D"
                ),
                end_date=np.datetime_as_string(kube.time.values[-1], unit="D"),
            )
        else:
            FILENAME_TEMPLATE = "{ncvar_name}_VHR-PRO_IT2km_CMCC-CM_{product_id}_CCLM5-0-9_1hr_{request_id}"
            ncvar_name = kube.fields[var_names[0]].ncvar
            return FILENAME_TEMPLATE.format(
                product_id=message.product_id,
                request_id=message.request_id,
                ncvar_name=ncvar_name,
            )
    else:
        if is_time_range:
            FILENAME_TEMPLATE = "VHR-PRO_IT2km_CMCC-CM_{product_id}_CCLM5-0-9_1hr_{start_date}_{end_date}_{request_id}"
            return FILENAME_TEMPLATE.format(
                product_id=message.product_id,
                request_id=message.request_id,
                start_date=np.datetime_as_string(
                    kube.time.values[0], unit="D"
                ),
                end_date=np.datetime_as_string(kube.time.values[-1], unit="D"),
            )
        else:
            FILENAME_TEMPLATE = (
                "VHR-PRO_IT2km_CMCC-CM_{product_id}_CCLM5-0-9_1hr_{request_id}"
            )
            return FILENAME_TEMPLATE.format(
                product_id=message.product_id,
                request_id=message.request_id,
            )


def rcp85_filename_condition(kube: DataCube, message: Message) -> bool:
    return (
        message.dataset_id == "climate-projections-rcp85-downscaled-over-italy"
    )


def get_history_message():
    return (
        f"Generated by CMCC DDS version 0.9.0 {str(datetime.datetime.now())}"
    )


def persist_datacube(
    kube: DataCube,
    message: Message,
    base_path: str | os.PathLike,
) -> str | os.PathLike:
    if rcp85_filename_condition(kube, message):
        path = get_file_name_for_climate_downscaled(kube, message)
    else:
        var_names = list(kube.fields.keys())
        if len(kube) == 1:
            path = "_".join(
                [
                    var_names[0],
                    message.dataset_id,
                    message.product_id,
                    message.request_id,
                ]
            )
        else:
            path = "_".join(
                [message.dataset_id, message.product_id, message.request_id]
            )
    kube._properties["history"] = get_history_message()
    if isinstance(message.content, GeoQuery):
        format = message.content.format
    else:
        format = "netcdf"
    match format:
        case "netcdf":
            full_path = os.path.join(base_path, f"{path}.nc")
            kube.to_netcdf(full_path)
        case "geojson":
            full_path = os.path.join(base_path, f"{path}.json")
            kube.to_geojson(full_path)
        case _:
            raise ValueError(f"format `{format}` is not supported")
    return full_path


def persist_dataset(
    dset: Dataset,
    message: Message,
    base_path: str | os.PathLike,
):
    def _get_attr_comb(dataframe_item, attrs):
        return "_".join([dataframe_item[attr_name] for attr_name in attrs])

    def _persist_single_datacube(dataframe_item, base_path, format):
        dcube = dataframe_item[dset.DATACUBE_COL]
        if isinstance(dcube, Delayed):
            dcube = dcube.compute()
        if len(dcube) == 0:
            return None
        for field in dcube.fields.values():
            if 0 in field.shape:
                return None
        attr_str = _get_attr_comb(dataframe_item, dset._Dataset__attrs)
        var_names = list(dcube.fields.keys())
        if len(dcube) == 1:
            path = "_".join(
                [
                    var_names[0],
                    message.dataset_id,
                    message.product_id,
                    attr_str,
                    message.request_id,
                ]
            )
        else:
            path = "_".join(
                [
                    message.dataset_id,
                    message.product_id,
                    attr_str,
                    message.request_id,
                ]
            )
        match format:
            case "netcdf":
                full_path = os.path.join(base_path, f"{path}.nc")
                dcube.to_netcdf(full_path)
            case "geojson":
                full_path = os.path.join(base_path, f"{path}.json")
                dcube.to_geojson(full_path)
        return full_path

    if isinstance(message.content, GeoQuery):
        format = message.content.format
    else:
        format = "netcdf"
    datacubes_paths = dset.data.apply(
        _persist_single_datacube, base_path=base_path, format=format, axis=1
    )
    paths = datacubes_paths[~datacubes_paths.isna()]
    if len(paths) == 0:
        return None
    elif len(paths) == 1:
        return paths.iloc[0]
    zip_name = "_".join(
        [message.dataset_id, message.product_id, message.request_id]
    )
    path = os.path.join(base_path, f"{zip_name}.zip")
    with ZipFile(path, "w") as archive:
        for file in paths:
            archive.write(file, arcname=os.path.basename(file))
    for file in paths:
        os.remove(file)
    return path


async def process(message: Message, compute: bool):
    res_path = os.path.join(_BASE_DOWNLOAD_PATH, message.request_id)
    os.makedirs(res_path, exist_ok=True)
    match message.type:
        case MessageType.QUERY:
            kube = Datastore().query(
                message.dataset_id,
                message.product_id,
                message.content,
                compute,
            )
        case MessageType.WORKFLOW:
            kube = Workflow.from_tasklist(message.content).compute()
        case _:
            raise ValueError("unsupported message type")
    if isinstance(kube, Field):
        kube = DataCube(
            fields=[kube],
            properties=kube.properties,
            encoding=kube.encoding,
        )
    match kube:
        case DataCube():
            return persist_datacube(kube, message, base_path=res_path)
        case Dataset():
            return persist_dataset(kube, message, base_path=res_path)
        case _:
            raise TypeError(
                "expected geokube.DataCube or geokube.Dataset, but passed"
                f" {type(kube).__name__}"
            )


class Executor(metaclass=LoggableMeta):
    _LOG = logging.getLogger("geokube.Executor")

    def __init__(self, broker, store_path):
        self._store = store_path
        broker_conn = pika.BlockingConnection(
            pika.ConnectionParameters(host=broker, heartbeat=10),
        )
        self._conn = broker_conn
        self._channel = broker_conn.channel()
        self._db = DBManager()

    def create_dask_cluster(self, dask_cluster_opts: dict = None):
        if dask_cluster_opts is None:
            dask_cluster_opts = {}
            dask_cluster_opts["scheduler_port"] = int(
                os.getenv("DASK_SCHEDULER_PORT", 8188)
            )
            dask_cluster_opts["processes"] = True
            port = int(os.getenv("DASK_DASHBOARD_PORT", 8787))
            dask_cluster_opts["dashboard_address"] = f":{port}"
            dask_cluster_opts["n_workers"] = 1
            dask_cluster_opts["memory_limit"] = "auto"
        self._worker_id = self._db.create_worker(
            status="enabled",
            dask_scheduler_port=dask_cluster_opts["scheduler_port"],
            dask_dashboard_address=dask_cluster_opts["dashboard_address"],
        )
        self._LOG.info(
            "creating Dask Cluster with options: `%s`",
            dask_cluster_opts,
            extra={"track_id": self._worker_id},
        )
        #dask_cluster = LocalCluster(
        #    n_workers=dask_cluster_opts['n_workers'],
            #scheduler_port=dask_cluster_opts["scheduler_port"],
            #dashboard_address=dask_cluster_opts["dashboard_address"],
            #memory_limit=dask_cluster_opts["memory_limit"],
        #    threads_per_worker=1
        #)
        self._LOG.info(
            "not creating Dask Client...", extra={"track_id": self._worker_id}
        )
        #self._dask_client = Client(dask_cluster)
        #self._nanny = Nanny(self._dask_client.cluster.scheduler.address)

    def maybe_restart_cluster(self, status: RequestStatus):
        if status is RequestStatus.TIMEOUT:
            self._LOG.info("recreating the cluster due to timeout")
            self._dask_client.cluster.close()
            self.create_dask_cluster()
        if self._dask_client.cluster.status is Status.failed:
            self._LOG.info("attempt to restart the cluster...")
            try:
                asyncio.run(self._nanny.restart())
            except Exception as err:
                self._LOG.error(
                    "couldn't restart the cluster due to an error: %s", err
                )
                self._LOG.info("closing the cluster")
                self._dask_client.cluster.close()
        if self._dask_client.cluster.status is Status.closed:
            self._LOG.info("recreating the cluster")
            self.create_dask_cluster()

    def ack_message(self, channel, delivery_tag):
        """Note that `channel` must be the same pika channel instance via which
        the message being ACKed was retrieved (AMQP protocol constraint).
        """
        if channel.is_open:
            channel.basic_ack(delivery_tag)
        else:
            self._LOG.info(
                "cannot acknowledge the message. channel is closed!"
            )
            pass

    def retry_until_timeout(
        self,
        future,
        message: Message,
        retries: int = 30,
        sleep_time: int = 10,
    ):
        assert retries is not None, "`retries` cannot be `None`"
        assert sleep_time is not None, "`sleep_time` cannot be `None`"
        status = fail_reason = location_path = None
        try:
            self._LOG.debug(
                "attempt to get result for the request",
                extra={"track_id": message.request_id},
            )
            for _ in range(retries):
                if future.done():
                    self._LOG.debug(
                        "result is done",
                        extra={"track_id": message.request_id},
                    )
                    location_path = future.result()
                    status = RequestStatus.DONE
                    self._LOG.debug(
                        "result save under: %s",
                        location_path,
                        extra={"track_id": message.request_id},
                    )
                    break
                self._LOG.debug(
                    f"result is not ready yet. sleeping {sleep_time} sec",
                    extra={"track_id": message.request_id},
                )
                time.sleep(sleep_time)
            else:
                self._LOG.info(
                    "processing timout",
                    extra={"track_id": message.request_id},
                )
                future.cancel()
                status = RequestStatus.TIMEOUT
                fail_reason = "Processing timeout"
        except Exception as e:
            self._LOG.error(
                "failed to get result due to an error: %s",
                e,
                exc_info=True,
                stack_info=True,
                extra={"track_id": message.request_id},
            )
            status = RequestStatus.FAILED
            fail_reason = f"{type(e).__name__}: {str(e)}"
        return location_path, status, fail_reason

    def handle_message(self, connection, channel, delivery_tag, body):
        message: Message = Message(body)
        self._LOG.debug(
            "executing query: `%s`",
            message.content,
            extra={"track_id": message.request_id},
        )

        # TODO: estimation size should be updated, too
        self._db.update_request(
            request_id=message.request_id,
            worker_id=self._worker_id,
            status=RequestStatus.RUNNING,
        )

        self._LOG.debug(
            "submitting job for workflow request",
            extra={"track_id": message.request_id},
        )
        #future = self._dask_client.submit(
        #    process,
        #    message=message,
        #    compute=False,
        #)

        future = asyncio.run(process(message,compute=False))

        location_path, status, fail_reason = self.retry_until_timeout(
            future,
            message=message,
            retries=int(os.environ.get("RESULT_CHECK_RETRIES")),
        )
        self._db.update_request(
            request_id=message.request_id,
            worker_id=self._worker_id,
            status=status,
            location_path=location_path,
            size_bytes=self.get_size(location_path),
            fail_reason=fail_reason,
        )
        self._LOG.debug(
            "acknowledging request", extra={"track_id": message.request_id}
        )
        cb = functools.partial(self.ack_message, channel, delivery_tag)
        connection.add_callback_threadsafe(cb)

        #self.maybe_restart_cluster(status)
        self._LOG.debug(
            "request acknowledged", extra={"track_id": message.request_id}
        )

    def on_message(self, channel, method_frame, header_frame, body, args):
        (connection, threads) = args
        delivery_tag = method_frame.delivery_tag
        t = threading.Thread(
            target=self.handle_message,
            args=(connection, channel, delivery_tag, body),
        )
        t.start()
        threads.append(t)

    def subscribe(self, etype):
        self._LOG.debug(
            "subscribe channel: %s_queue", etype, extra={"track_id": "N/A"}
        )
        self._channel.queue_declare(queue=f"{etype}_queue", durable=True)
        self._channel.basic_qos(prefetch_count=1)

        threads = []
        on_message_callback = functools.partial(
            self.on_message, args=(self._conn, threads)
        )

        self._channel.basic_consume(
            queue=f"{etype}_queue", on_message_callback=on_message_callback
        )

    def listen(self):
        while True:
            self._channel.start_consuming()

    def get_size(self, location_path):
        if location_path and os.path.exists(location_path):
            return os.path.getsize(location_path)
        return None


if __name__ == "__main__":
    broker = os.getenv("BROKER_SERVICE_HOST", "broker")
    executor_types = os.getenv("EXECUTOR_TYPES", "query").split(",")
    store_path = os.getenv("STORE_PATH", ".")

    executor = Executor(broker=broker, store_path=store_path)
    print("channel subscribe")
    for etype in executor_types:
        if etype == "query":
            #TODO: create dask cluster with options
            executor.create_dask_cluster()

        executor.subscribe(etype)

    print("waiting for requests ...")
    executor.listen()
