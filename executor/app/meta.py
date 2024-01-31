"""Module with `LoggableMeta` metaclass"""

import os
import logging


class LoggableMeta(type):
    """Metaclass for dealing with logger levels and handlers"""

    def __new__(cls, child_cls, bases, namespace):
        # NOTE: method is called while creating a class, not an instance!
        res = super().__new__(cls, child_cls, bases, namespace)
        if hasattr(res, "_LOG"):
            format_ = os.environ.get(
                "LOGGING_FORMAT",
                "%(asctime)s %(name)s %(levelname)s %(lineno)d"
                " %(track_id)s %(message)s",
            )
            formatter = logging.Formatter(format_)
            logging_level = os.environ.get("LOGGING_LEVEL", "INFO")
            res._LOG.setLevel(logging_level)
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(logging_level)
            res._LOG.addHandler(stream_handler)
            for handler in logging.getLogger("geokube").handlers:
                handler.setFormatter(formatter)
        return res
