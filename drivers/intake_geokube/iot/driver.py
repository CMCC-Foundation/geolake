"""Driver for IoT data."""

import json
from collections import deque
from datetime import datetime
from typing import NoReturn

import dateparser
import numpy as np
import pandas as pd
import streamz

from ..base import AbstractBaseDriver
from ..queries.geoquery import GeoQuery

d: deque = deque(maxlen=1)


def _build(data_model: dict) -> pd.DataFrame:
    model_dict = {
        data_model.get("time", ""): pd.to_datetime(
            "01-01-1970 00:00:00", format="%d-%m-%Y %H:%M:%S"
        ),
        data_model.get("latitude", ""): [0.0],
        data_model.get("longitude", ""): [0.0],
    }
    for f in data_model.get("filters", []):
        model_dict[f] = [0]
    for v in data_model.get("variables", []):
        model_dict[v] = [0]
    df_model = pd.DataFrame(model_dict)
    df_model = df_model.set_index(data_model.get("time", ""))
    return df_model


def _mqtt_preprocess(df, msg) -> pd.DataFrame:
    payload = json.loads(msg.payload.decode("utf-8"))
    if ("uplink_message" not in payload) or (
        "frm_payload" not in payload["uplink_message"]
    ):
        return df
    data = payload["uplink_message"]["decoded_payload"]["data_packet"][
        "measures"
    ]
    date_time = pd.to_datetime(
        datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        format="%d-%m-%Y %H:%M:%S",
    )
    data["device_id"] = payload["end_device_ids"]["device_id"]
    data["string_type"] = 9
    data["cycle_duration"] = payload["uplink_message"]["decoded_payload"][
        "data_packet"
    ]["timestamp"]
    data["sensor_time"] = pd.to_datetime(
        payload["received_at"], format="%Y-%m-%dT%H:%M:%S.%fZ"
    )
    data["latitude"] = data["latitude"] / 10**7
    data["longitude"] = data["longitude"] / 10**7
    data["AirT"] = data["AirT"] / 100
    data["AirH"] = data["AirH"] / 100
    data["surfaceTemp"] = 2840 / 100
    row = pd.Series(data, name=date_time)
    df = df._append(row)  # pylint: disable=protected-access
    return df


class IotDriver(AbstractBaseDriver):
    """Driver class for IoT data."""

    name: str = "iot_driver"
    version: str = "0.1b0"

    def __init__(
        self,
        mqtt_kwargs,
        time_window,
        data_model,
        start=False,
        metadata=None,
        **kwargs,
    ):
        super().__init__(metadata=metadata)
        self.mqtt_kwargs = mqtt_kwargs
        self.kwargs = kwargs
        self.stream = None
        self.time_window = time_window
        self.start = start
        self.df_model = _build(data_model)

    def _get_schema(self):
        if not self.stream:
            self.log.debug("creating stream...")
            stream = streamz.Stream.from_mqtt(**self.mqtt_kwargs)
            self.stream = stream.accumulate(
                _mqtt_preprocess, returns_state=False, start=pd.DataFrame()
            ).to_dataframe(example=self.df_model)
            self.stream.stream.sink(d.append)
        if self.start:
            self.log.info("streaming started...")
            self.stream.start()
        return {"stream": str(self.stream)}

    def read(self):
        """Read IoT data."""
        self.log.info("reading stream...")
        self._get_schema()
        return self.stream

    def load(self) -> NoReturn:
        """Load IoT data."""
        self.log.error("loading entire product is not supported for IoT data")
        raise NotImplementedError(
            "loading entire product is not supported for IoT data"
        )

    def process(self, query: GeoQuery):
        """Process IoT data with the passed query.

        Parameters
        ----------
        query : intake_geokube.GeoQuery
            A query to use

        Returns
        -------
        stream  : streamz.dataframe.DataFrame
            A DataFrame object with streamed content
        """
        df = d[0]
        if not query:
            self.log.info(
                "method 'process' called without query. processing skipped."
            )
            return df
        if query.time:
            if not isinstance(query.time, slice):
                self.log.error(
                    "expected 'query.time' type is slice but found %s",
                    type(query.time),
                )
                raise TypeError(
                    "expected 'query.time' type is slice but found"
                    f" {type(query.time)}"
                )
            self.log.info("querying by time: %s", query.time)
            df = df[query.time.start : query.time.stop]
        else:
            self.log.info(
                "getting latest data for the predefined tie window: %s",
                self.time_window,
            )
            start = dateparser.parse(f"NOW - {self.time_window}")
            stop = dateparser.parse("NOW")
            df = df[start:stop]  # type: ignore[misc]
        if query.filters:
            self.log.info("filtering with: %s", query.filters)
            mask = np.logical_and.reduce(
                [df[k] == v for k, v in query.filters.items()]
            )
            df = df[mask]
        if query.variable:
            self.log.info("selecting variables: %s", query.variable)
            df = df[query.variable]
        return df
