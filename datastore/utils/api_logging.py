import os
from typing import Literal
import logging as default_logging


def get_geolake_logger(
    name: str,
    level: Literal["debug", "info", "warning", "error", "critical"] = "info",
):
    """Get GeoLake logger with the expected format, handlers and formatter.

    Parameters
    ----------
    name : str
        Name of the logger
    level : str, default="info"
        Value of the logging level. One out of ["debug", "info", "warn",
        "error", "critical"].
        Logging level is taken from the
        enviornmental variable `LOGGING_FORMAT`. If this variable is not defined,
        the value of the `level` argument is used.

    Returns
    -------
    log : logging.Logger
        Logger with the handlers set
    """
    log = default_logging.getLogger(name)
    format_ = os.environ.get(
        "LOGGING_FORMAT",
        "%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    formatter = default_logging.Formatter(format_)
    logging_level = os.environ.get("LOGGING_LEVEL", level.upper())
    log.setLevel(logging_level)
    stream_handler = default_logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging_level)
    log.addHandler(stream_handler)
    return log
