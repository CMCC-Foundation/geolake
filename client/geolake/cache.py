"""This module contains simple query-hash-based cache mechanism."""

import os
import json
from typing import Mapping, Optional, Iterable, Union
from uuid import uuid4
from dataclasses import dataclass, field
import pickle
import shutil

from geokube.core.datacube import DataCube
import hashlib


@dataclass
class CacheManager:
    cache_dir: str = field(kw_only=True)
    disabled: bool = field(default=False, init=True, kw_only=True)
    cache_config: str = field(default=".config", init=False)
    _cache: Mapping[str, str] = field(init=False)

    def __post_init__(self):
        self._init()
        self._cache = self._read_cache() if not self.disabled else {}

    def _init(self) -> None:
        self._cache = {}
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        if os.path.exists(os.path.join(self.cache_dir, self.cache_config)):
            return
        self._update_cache_config()

    def _update_cache_config(self) -> None:
        with open(os.path.join(self.cache_dir, self.cache_config), "wb") as file:
            pickle.dump(self._cache, file=file)

    def _read_cache(self) -> dict:
        with open(os.path.join(self.cache_dir, self.cache_config), "rb") as file:
            return pickle.load(file)

    def _compute_hash(
        self, dataset_id: str, product_id: str, request: dict
    ) -> int:
        return hashlib.sha256(
            json.dumps(
                dict(**{"dataset_id": dataset_id, "product_id": product_id}, **request)
            ).encode()
        ).hexdigest()

    def _maybe_get_file_from_cache(
        self, dataset_id: str, product_id: str, request: dict
    ) -> Optional[str]:
        query_hash: int = self._compute_hash(dataset_id, product_id, request)
        return self._cache.get(query_hash)

    def add_to_cache(
        self,
        dataset_id: str,
        product_id: str,
        request: dict,
        target: Union[Iterable[str], str],
        *,
        overwrite: bool = False,
    ) -> None:
        if self.disabled:
            return
        query_hash: int = self._compute_hash(dataset_id, product_id, request)
        if query_hash in self._cache and not overwrite:
            return
        if isinstance(target, list):
            cache_files = []
            for f in target:
                _, ext = os.path.splitext(f)
                res_file = f"{uuid4()}{ext}"
                cache_files.append(res_file)
                shutil.move(f, os.path.join(self.cache_dir, res_file))
            self._cache[query_hash] = cache_files
        elif isinstance(target, str):
            _, ext = os.path.splitext(target)
            res_file = f"{uuid4()}{ext}"
            shutil.move(target, os.path.join(self.cache_dir, res_file))
            self._cache[query_hash] = res_file
        self._update_cache_config()

    def maybe_get_from_cache(
        self, dataset_id: str, product_id: str, request: dict
    ) -> Union[DataCube, Iterable[DataCube], None]:
        target: Union[str, Iterable[str]] = self._maybe_get_file_from_cache(
            dataset_id=dataset_id, product_id=product_id, request=request
        )
        if self.disabled:
            return        
        if not target:
            return
        if isinstance(target, list):
            ds_list = []
            for f in target:
                ds = xr.open_dataset(os.path.join(self.cache_dir, f), decode_coords='all')
                ds_list.append(ds)
            if len(ds_list) == 1:
                return ds_list[0]
            return ds_list
        elif isinstance(target, str):
            return xr.open_dataset(os.path.join(self.cache_dir, target), decode_coords='all')
        else:
            raise TypeError
