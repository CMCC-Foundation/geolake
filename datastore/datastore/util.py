"""Utils module"""

from functools import wraps
import datetime
import logging


def log_execution_time(logger: logging.Logger):
    """Decorator logging execution time of the method or function"""

    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwds):
            exec_start_time = datetime.datetime.now()
            try:
                return func(*args, **kwds)
            finally:
                exec_time = datetime.datetime.now() - exec_start_time
                logger.info(
                    "execution of '%s' function from '%s' package took %s",
                    func.__name__,
                    func.__module__,
                    exec_time,
                )

        return wrapper

    return inner
