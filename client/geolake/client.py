# (C) Copyright 2018 ECMWF.
# (C) Copyright 2019 - 2023 CMCC Foundation.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation nor
# does it submit to any jurisdiction.
# In applying this licence, CMCC Foundation does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation nor
# does it submit to any jurisdiction.

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
    annotations
)
import dis

import pickle
import json
import time
import os
import logging
import requests
import zipfile
import shutil
from typing import Any, Union, Iterable
import urllib3
from geokube.backend.netcdf import open_datacube

from .cache import CacheManager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def str2bool(s: str, default: Any = False) -> bool:
    if isinstance(s, str):
        return s.lower() in ("1", "yes", "y", "true")
    return default

def bytes_to_string(n):
    u = ["", "K", "M", "G", "T", "P"]
    i = 0
    while n >= 1024:
        n /= 1024.0
        i += 1
    return "%g%s" % (int(n * 10 + 0.5) / 10.0, u[i])


def read_config(path):
    """Read configuration file with url and key


    Parameters
    ----------
    path : str
        Path to configuration file
    """
    config = {}
    with open(path, mode="rt") as f:
        for line in f.readlines():
            if ":" in line:
                k, v = line.strip().split(":", 1)
                if k in ("url", "key", "verify"):
                    config[k] = v.strip()
    return config


class _Result:
    def __init__(self, client, request_id, auth_token):
        self.request_id = request_id
        self._url = client.url
        self.target_path = None
        self._is_zip = False

        self.session = client.session
        self.robust = client.robust
        self.verify = client.verify
        self.cleanup = client.delete

        self.debug = client.debug
        self.info = client.info
        self.warning = client.warning
        self.error = client.error

        self._deleted = False
        self.auth_token = auth_token

        self._download_endpoint = "/download/{request_id}"
        self._check_size_endpoint = "/requests/{request_id}/size"

    @property
    def _download_url(self):
        return "".join(
            [
                self._url,
                self._download_endpoint.format(request_id=self.request_id),
            ]
        )

    @property
    def _check_size_url(self):
        return "".join(
            [
                self._url,
                self._check_size_endpoint.format(request_id=self.request_id),
            ]
        )

    def _get_resulting_size(self):
        return self.robust(self.session.get)(
            self._check_size_url, verify=self.verify
        )

    def _maybe_handle_zip(self, response):
        self._is_zip = response.headers["content-type"] == "application/zip"

    def _download(self, url, target):
        size_res = self._get_resulting_size()
        if size_res.status_code != 200:
            raise RuntimeError(
                "Could not get size of the resulting file due to an error:"
                f" {size_res.json()}"
            )
        size = size_res.json()
        self.info(
            "Downloading %s to %s (%s)", url, target, bytes_to_string(size)
        )
        start = time.time()
        res = self.robust(requests.get)(
            url, stream=True, verify=self.verify, headers=self.auth_token
        )
        self._maybe_handle_zip(res)
        if self._is_zip:
            target = "".join([target, ".zip"])
        try:
            res.raise_for_status()

            total = 0
            with open(target, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
        finally:
            res.close()

        if total != size:
            raise Exception(
                f"Download failed: downloaded {total} byte(s) out of {size}"
            )

        elapsed = time.time() - start
        if elapsed:
            self.info("Download rate %s/s", bytes_to_string(size / elapsed))

        self.target_path = target
        return target

    def download(self, target=None):
        self.debug("Downloading from %s", self._download_url)
        return self._download(self._download_url, target)
    
    def _maybe_unzip(self):
        if self._is_zip:
            with zipfile.ZipFile(self.target_path, "r") as zip_ref:
                self.target_path = self.target_path.split(".")[0]
                zip_ref.extractall(self.target_path)

    def get_files(self) -> Union[str, Iterable[str]]:
        self._maybe_unzip()
        if os.path.isdir(self.target_path):
            return [os.path.join(self.target_path, f) for f in os.listdir(self.target_path)]
        return self.target_path

    def dataset(self):
        self.debug("Location %s", self.target_path)
        if self.target_path is None:
            raise RuntimeError(
                "No file found. Downloading could have not finished yet or it"
                " failed."
            )
        self._maybe_unzip()
        if os.path.isdir(self.target_path):
            ds_list = []
            for f in os.listdir(self.target_path):
                ds = open_datacube(os.path.join(self.target_path, f), engine='netcdf4')
                ds_list.append(ds)
            if len(ds_list) == 1:
                return ds_list[0]
            return ds_list
        return open_datacube(self.target_path, engine='netcdf4')
    
class EnvVarNames:
    RC_FILE: str = "GEOLAKE_RC"
    URL: str = "GEOLAKE_API_URL"
    KEY: str = "GEOLAKE_API_KEY"
    CACHEDIR: str = "GEOLAKE_CACHEDIR"  
    DISABLE_CACHE: str = "GEOLAKE_CACHE_DISABLE"  

class Config:
    """Configuration class.

    The configuration defined in the `.geolakerc` file overwrites those
    defined using environmental variables."""

    _RC_FILENAME: str = ".geolakerc"
    _CACHE_FILENAME: str = ".cache"
    url: None | str = None
    key: None | str = None
    cachedir: None | str = None
    verify: None | int = None

    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        dotrc = os.environ.get(
            EnvVarNames.RC_FILE,
            os.path.expanduser(os.path.join("~", Config._RC_FILENAME)),
        )
        self._init_conf_with_env_vars()
        self._maybe_overwrite_from_rc_file(dotrc)
        self._maybe_apply_defaults()
        self._apply_user_defined(url=url, key=key)

    def _apply_user_defined(self, url, key) -> None:
        if url:
            self.url = url
        if key:
            self.key = key

    def _maybe_apply_defaults(self) -> None:
        if self.verify is None:
            self.verify = 1
        if not self.cachedir:
            self.cachedir = os.path.expanduser(
                os.path.join("~", Config._CACHE_FILENAME)
            )

    def _init_conf_with_env_vars(self) -> None:
        self.url = os.environ.get(EnvVarNames.URL)
        self.key = os.environ.get(EnvVarNames.KEY)
        self.cachedir = os.environ.get(EnvVarNames.CACHEDIR)

    def _maybe_overwrite_from_rc_file(self, rcfile: str) -> None:
        if os.path.exists(rcfile): 
            config = read_config(rcfile)
        else:
            config = {}
        if not self.key:
            self.key = config.get("key")
        if not self.url:
            self.url = config.get("url")
        if not self.verify:
            verify_ = config.get("verify")
            self.verify = int(verify_) if verify_ else None
        if not self.cachedir:
            self.cachedir = config.get("cachedir")


class Client:
    """
    Represents the client.

    Parameters
    ----------
    url : str, optional
        The URL.
        Default ``os.environ.get('GEOLAKE_API_URL')``

    key : str, optional
        The key.
        Default ``os.environ.get('GEOLAKE_API_KEY')``

    quiet : bool, optional
        Whether to use quite mode.
        Default ``False``.

    debug : bool, optional
        Whether to use debug mode.
        Default ``False``.

    verify : bool or None, optional
        Whether to verify.
        Default ``None``.

    timeout : int or None, optional
        The session timeout, in seconds. If ``None``, no timeout.
        Default ``None``.

    full_stack : bool, optional
        Whether it is fullstack.
        Default ``False``.

    delete : bool, optional
        Whether to delete.
        Default ``True``.

    retry_max : int, optional
        Maximal number of retry attempts.
        Default ``500``.

    sleep_max : int, optional
        Maximal sleep time, in seconds.
        Default ``120``.

    info_callback : callable or None, optional
        The callback for information.
        Default ``None``.

    warning_callback=None : callable or None, optional
        The callback for warnings.
        Default ``None``.

    error_callback=None : callable or None, optional
        The callback for errors.
        Default ``None``.

    debug_callback=None : callable or None, optional
        The callback for debugging.
        Default ``None``.

    """

    logger = logging.getLogger("geolake")

    def __init__(
        self,
        url=None,
        key=None,
        direct_path=False,
        quiet=False,
        debug=False,
        verify=None,
        timeout=None,
        full_stack=False,
        delete=True,
        retry_max=500,
        sleep_max=120,
        info_callback=None,
        warning_callback=None,
        error_callback=None,
        debug_callback=None,
    ):
        """Initialize :class:`Client`."""
        if not quiet:
            if debug:
                level = logging.DEBUG
            else:
                level = logging.INFO

            logging.basicConfig(
                level=level, format="%(asctime)s %(levelname)s %(message)s"
            )
        config = Config()
        self.url = config.url
        self.key = config.key
        self.verify = config.verify
        self.cache: CacheManager = CacheManager(
            cache_dir=config.cachedir,
            disabled=str2bool(os.environ.get(EnvVarNames.DISABLE_CACHE), default=True))
        self.cachedir = config.cachedir

        if self.url is None or self.key is None:
            raise Exception("Missing/incomplete configuration file")

        self.direct_path = direct_path

        self.quiet = quiet
        self.verify = True if verify else False
        self.timeout = timeout
        self.sleep_max = sleep_max
        self.retry_max = retry_max
        self.full_stack = full_stack
        self.delete = delete
        self.last_state = None

        self.debug_callback = debug_callback
        self.warning_callback = warning_callback
        self.info_callback = info_callback
        self.error_callback = error_callback

        self.session = requests.Session()
        self.auth_token = {"User-Token": self.key}
        self.session.headers.update(self.auth_token)
        self.debug(
            "GEOLAKE CLIENT %s",
            dict(
                url=self.url,
                direct_path=self.direct_path,
                key=self.key,
                quiet=self.quiet,
                verify=self.verify,
                timeout=self.timeout,
                sleep_max=self.sleep_max,
                retry_max=self.retry_max,
                full_stack=self.full_stack,
                delete=self.delete,
            ),
        )

    def _submit(self, url, request):
        session = self.session

        self.info("Sending request to %s", url)
        self.debug("POST %s %s", url, json.dumps(request))

        reply = self.robust(session.post)(
            url, json=request, verify=self.verify
        )
        return reply

    def _get(self, url):
        session = self.session

        self.info("Sending GET request to %s", url)
        self.debug("GET %s %s", url)

        reply = self.robust(session.get)(url, verify=self.verify)
        return reply

    def _maybe_handle_fails_on_4xx_code(self, response):
        if response.status_code in [400, 401]:
            self.logger.error(response.json()["detail"])
            return True
        return False

    def _maybe_handle_fails_on_200_code(self, response):
        if response.status_code == 200:
            msg = response.json()
            if isinstance(msg, int):
                self.logger.info("Request is scheduled with ID: %s", msg)
                return False
            if msg["status"] == "FAILED":
                self.logger.error(
                    "Request execution failed due to an error: %s",
                    msg["fail_reason"],
                )
                return True
        return False

    def retrieve(self, dataset_id, product_id, request, target=None):
        """
        Retrieve the dataset.

        Creates and saves the dataset that contains the desired data
        from the CMCC catalogs.

        Parameters
        ----------
        name : str
            The name of the dataset.

        request : dict-like
            The arguments passed with the request. Possible options are:

                variable : str, array-like of str
                    The name(s) of the variable(s) that should be loaded
                    from the dataset.

                year, month, day, time : array-like of str or int
                    Years, months, days, and times for which the data
                    and coordinates are loaded.

                area : array-like or dict-like, optional
                    The northern, western, southern, and eastern
                    coordinate bounds of the analyzed area, in degrees.

                    If sequence, it should hold four values in the
                    following order:

                    * north bound latitude coordinate
                    * west bound longitude coordinate
                    * south bound latitude coordinate
                    * east bound longitude coordinate

                    If mapping, the order is not important, but it
                    should hold four key-value pairs:

                    * ``'north':`` north bound latitude coordinate
                    * ``'west':`` west bound longitude coordinate
                    * ``'south':`` south bound latitude coordinate
                    * ``'east':`` east bound longitude coordinate

                reversed_latitude : bool, optional
                    ``True`` if the values of latitude are aranged from
                    south to north and ``False`` otherwise.
                    Default: ``False``.
                    Ignored if `area` is omitted.

                reversed_longitude : bool, optional
                    ``True`` if the values of longitude are aranged from
                    east to west and ``False`` otherwise.
                    Default: ``False``.
                    Ignored if `area` is omitted.

                location : array-like or dict-like, optional
                    The latitude and longitude of the single point, in
                    degrees.

                    If sequence, it should hold two values in the
                    following order:

                    * latitude coordinate
                    * longitude coordinate

                    If mapping, the order is not important, but it
                    should hold two key-value pairs:

                    * ``'latitude':`` latitude coordinate
                    * ``'longitude':`` longitude coordinate

                    Ignored if `area` is provided.

                location_method : {'pad', 'backfill', 'nearest'}, optional
                    The method to use when choosing an inexact location.
                    Default: ``'nearest'``.
                    Ignored if `area` is provided or `location` is
                    omitted.

                format : {'netcdf', 'pickle'}, optional
                    The format of the file to save the data and
                    coordinates.
                    It should match the extension of `target`.

        target : str or None, optional.
            The name of the target file where the dataset is saved.

        Raises
        ------
        Exception
            If any of the following problems occur:

            * Unauthorized access
            * Invalid request
            * Resource not found
            * Unknown API state

        Examples
        --------
        In order to retrieve some data, it is required to create an
        instance of :class:`Client` and call :meth:`retrieve`:

        >>> import geolake
        >>> client = geolake.Client()
        >>> client.retrieve(
        ...     name='era5',
        ...     request={
        ...         'variable': 'tp',
        ...         'product_type': 'reanalysis',
        ...         'year': ['2005', '2006', '2012', '2018'],
        ...         'month': ['01', '11', '12'],
        ...         'day': ['01', '02', '31'],
        ...         'time': ['00:00', '06:00', '12:00', '18:00'],
        ...         'area': [55.4, 8.0, 12.1, 23.0],
        ...         'format': 'netcdf',
        ...     },
        ...     target='era5_tp1.nc'
        ... )

        The values that correspond to the keys ``'year'``, ``'month'``,
        ``'day'``, and ``'time'`` can be integers as well, not
        necessarily sorted:

        >>> client.retrieve(
        ...     name='era5',
        ...     request={
        ...         'variable': 'tp',
        ...         'product_type': 'reanalysis',
        ...         'year': [2005, 2006, 2012, 2018],
        ...         'month': [11 , 12, 1],
        ...         'day': [1, 2, 31],
        ...         'time': [0, 6, 12, 18],
        ...         'area': [55.4, 8.0, 12.1, 23.0],
        ...         'format': 'netcdf',
        ...     },
        ...     target='era5_tp1.nc'
        ... )

        If the value of ``'time'`` is an array-like object of integers,
        its items are interpreted as hours.
        The value that corresponds to the key ``'area'`` can be defined
        with a dict-like object as well:

        >>> client.retrieve(
        ...     name='era5',
        ...     request={
        ...         'variable': 'tp',
        ...         'product_type': 'reanalysis',
        ...         'year': [2005, 2006, 2012, 2018],
        ...         'month': [11 , 12, 1],
        ...         'day': [1, 2, 31],
        ...         'time': [0, 6, 12, 18],
        ...         'area': {'east': 23.0, 'west': 8.0,
        ...                  'north': 55.4, 'south': 12.1},
        ...         'format': 'netcdf',
        ...     },
        ...     target='era5_tp1.nc'
        ... )

        If a single location is required, it can be defined by using the
        key ``'location'`` instead of ``'area'``:

        >>> client.retrieve(
        ...     name='era5',
        ...     request={
        ...         'variable': 'rr',
        ...         'product_type': 'reanalysis',
        ...         'year': [2005, 2006, 2012, 2018],
        ...         'month': [11 , 12, 1],
        ...         'day': [1, 2, 31],
        ...         'time': [0, 6, 12, 18],
        ...         'location': [55.68, 12.57],
        ...         'format': 'netcdf',
        ...     },
        ...     target='era5_rr.nc'
        ... )

        >>> client.retrieve(
        ...     name='era5',
        ...     request={
        ...         'variable': 'tp',
        ...         'product_type': 'reanalysis',
        ...         'year': [2005, 2006, 2012, 2018],
        ...         'month': [11 , 12, 1],
        ...         'day': [1, 2, 31],
        ...         'time': [0, 6, 12, 18],
        ...         'location': {'latitude': 55.68,
        ...                      'longitude': 12.57},
        ...         'format': 'netcdf',
        ...     },
        ...     target='era5_tp1.nc'
        ... )

        """
        assert dataset_id, "'dataset_id' cannot be 'None'"
        assert product_id, "'product_id' cannot be 'None'"
        session = self.session
        if "format" not in request:
            request["temp_file"] = target
        cached_target = self.cache.maybe_get_from_cache(dataset_id=dataset_id, product_id=product_id, request=request)
        if cached_target:
            return cached_target

        jreply = self._submit(
            f"{self.url}/datasets/{dataset_id}/{product_id}/execute",
            request,
        )
        self.info("Request is Submitted")
        if self._maybe_handle_fails_on_200_code(jreply):
            return
        if self._maybe_handle_fails_on_4xx_code(jreply):
            return
        job_reply = jreply.json()
        self.debug(f"JSON reply {job_reply}")
        try:
            request_id = int(job_reply)
        except ValueError:
            self.logger.error("API didn't return request ID!")
            return
        except TypeError:
            self.logger.error(
                "Processing failed due to an error: %s", job_reply
            )
            return
        request_status_url = f"{self.url}/requests/{request_id}/status"

        sleep = 1
        start = time.time()

        while True:
            reply = self.robust(session.get)(
                request_status_url, verify=self.verify
            )
            if self._maybe_handle_fails_on_200_code(reply):
                return
            msg = reply.json()
            self.debug("REPLY %s", reply)

            if reply.status_code != 200:
                self.logger.info(
                    "Submitting request failed due to en error: %s", msg
                )
                return

            assert (
                "status" in msg
            ), "'status' key is not included in response JSON!"

            if msg["status"] != self.last_state:
                self.info("Request is in %s state", msg["status"])
                self.last_state = msg["status"]

            if msg["status"] == "DONE":
                self.debug("Done: %s", reply.json())
                result = _Result(
                    self, request_id=request_id, auth_token=self.auth_token
                )
                import tempfile
                if target is None:
                    _target = tempfile.NamedTemporaryFile(delete=False).name
                else:
                    _target = target
                try:
                    result.download(_target)
                    self.cache.add_to_cache(
                        dataset_id=dataset_id, 
                        product_id=product_id, 
                        request=request, 
                        target=result.get_files(), overwrite=False)
                except RuntimeError as err:
                    self.logger.error(str(err))
                    return
    
                if target is not None:
                    return result
                else:
                    if self.cache.disabled:
                        return result.dataset()
                    else:
                        return self.cache.maybe_get_from_cache(dataset_id=dataset_id, product_id=product_id, request=request)

            if msg["status"] == "RUNNING" or msg["status"] == "PENDING":
                if self.timeout and (time.time() - start > self.timeout):
                    raise Exception("TIMEOUT")

                self.debug("Request ID is %s, sleep %s", request_id, sleep)
                time.sleep(sleep)
                sleep *= 1.5
                if sleep > self.sleep_max:
                    sleep = self.sleep_max

                continue
            if msg["status"] == "TIMEOUT":
                self.debug("Request timeout!")
                return
            raise Exception(f"Unknown API state [{reply.status_code}]")

    def datasets(self, dataset_name=None):
        """
        Retrieve details for the dataset of the given name or if dataset_name is None, returns
        names of all datasets available in the Catalog.

        Parameters
        ----------
        dataset_name : str
            The name of the dataset.

        Raises
        ------
        Exception
            If any of the following problems occur:

            * Unauthorized access
            * Invalid request
            * Resource not found
            * Unknown API state
        """
        if dataset_name is None:
            self.info("Names of all available datasets were requested")
            req_url = f"{self.url}/datasets"
        else:
            self.info(
                "Details requested for the dataset with the name"
                f" {dataset_name}"
            )
            req_url = f"{self.url}/datasets/{dataset_name}"

        jreply = self._get(req_url)
        self.info("Request is Submitted")

        job_reply = jreply.json()
        self.debug("JSON reply %s", job_reply)
        return job_reply

    def info(self, *args, **kwargs):
        """Handle info."""
        if self.info_callback:
            self.info_callback(*args, **kwargs)
        else:
            self.logger.info(*args, **kwargs)

    def warning(self, *args, **kwargs):
        """Handle warning."""
        if self.warning_callback:
            self.warning_callback(*args, **kwargs)
        else:
            self.logger.warning(*args, **kwargs)

    def error(self, *args, **kwargs):
        """Handle error."""
        if self.error_callback:
            self.error_callback(*args, **kwargs)
        else:
            self.logger.error(*args, **kwargs)

    def debug(self, *args, **kwargs):
        """Debug."""
        if self.debug_callback:
            self.debug_callback(*args, **kwargs)
        else:
            self.logger.debug(*args, **kwargs)

    def robust(self, call):
        """Define helper functions."""

        def retriable(code, reason):
            if code in [408, 429, 500, 503, 504]:
                return True
            return False

        def wrapped(*args, **kwargs):
            tries = 0
            while tries < self.retry_max:
                try:
                    res = call(*args, **kwargs)
                except requests.exceptions.ConnectionError as err:
                    res = None
                    self.warning(
                        "Recovering from connection error [%s], attemps %s"
                        " of %s",
                        err,
                        tries,
                        self.retry_max,
                    )

                if res is not None:
                    if not retriable(res.status_code, res.reason):
                        return res
                    try:
                        text = res.json()['detail']
                    except requests.exceptions.JSONDecodeError:
                        text = res.text
                    self.warning(
                        "Recovering from HTTP error [%s %s], attemps %s of %s",
                        res.status_code,
                        text,
                        tries,
                        self.retry_max,
                    )

                tries += 1

                self.warning("Retrying in %s seconds", self.sleep_max)
                time.sleep(self.sleep_max)

        return wrapped
