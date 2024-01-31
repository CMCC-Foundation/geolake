"""Module with functions call during API server startup"""

from utils.api_logging import get_dds_logger

from datastore.datastore import Datastore

log = get_dds_logger(__name__)


def _load_cache() -> None:
    log.info("loading cache started...")
    Datastore()._load_cache()
    log.info("cache loaded succesfully!")


all_onstartup_callbacks = [_load_cache]
