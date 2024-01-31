"""Module with util functions."""

from typing import Any, Collection, Hashable, Iterable

import dateparser
from pydantic.fields import FieldInfo

_TIME_COMBO_SUPPORTED_KEYS: tuple[str, ...] = (
    "year",
    "month",
    "day",
    "hour",
)

_BBOX_SUPPORTED_KEYS: tuple[str, ...] = (
    "north",
    "south",
    "west",
    "east",
)


def _validate_dict_keys(
    provided_keys: Iterable, supported_keys: Collection
) -> None:
    for provided_k in provided_keys:
        assert (
            provided_k in supported_keys
        ), f"key '{provided_k}' is not among supported ones: {supported_keys}"


def dict_to_slice(mapping: dict) -> slice:
    """Convert dictionary to slice."""
    mapping = mapping or {}
    assert "start" in mapping or "stop" in mapping, (
        "missing at least of of the keys ['start', 'stop'] required to"
        " construct slice object based on the dictionary"
    )
    if "start" in mapping and "NOW" in mapping["start"]:
        mapping["start"] = dateparser.parse(mapping["start"])
    if "stop" in mapping and "NOW" in mapping["stop"]:
        mapping["stop"] = dateparser.parse(mapping["stop"])
    return slice(
        mapping.get("start"),
        mapping.get("stop"),
        mapping.get("step"),
    )


def maybe_dict_to_slice(mapping: Any) -> slice:
    """Convert valid dictionary to slice or return the original one."""
    if "start" in mapping or "stop" in mapping:
        return dict_to_slice(mapping)
    return mapping


def slice_to_dict(slice_: slice) -> dict:
    """Convert slice to dictionary."""
    return {"start": slice_.start, "stop": slice_.stop, "step": slice_.step}


def assert_time_combo_dict(mapping: dict) -> dict:
    """Check if dictionary contains time-combo related keys."""
    _validate_dict_keys(mapping.keys(), _TIME_COMBO_SUPPORTED_KEYS)
    return mapping


def assert_bounding_box_dict(mapping: dict) -> dict:
    """Check if dictionary contains bounding-box related keys."""
    _validate_dict_keys(mapping.keys(), _BBOX_SUPPORTED_KEYS)
    return mapping


def split_extra_arguments(
    values: dict, fields: dict[str, FieldInfo]
) -> tuple[dict, dict]:
    """Split arguments to field-related and auxiliary."""
    extra_args: dict = {}
    field_args: dict = {}
    extra_args = {k: v for k, v in values.items() if k not in fields}
    field_args = {k: v for k, v in values.items() if k in fields}
    return (field_args, extra_args)


def find_value(
    content: dict | list, key: Hashable, *, recursive: bool = False
) -> Any:
    """Return value for a 'key' (recursive search)."""
    result = None
    if isinstance(content, dict):
        if key in content:
            return content[key]
        if not recursive:
            return result
        for value in content.values():
            if isinstance(value, (dict, list)):
                result = result or find_value(value, key, recursive=True)
    elif isinstance(content, list):
        for el in content:
            result = result or find_value(el, key, recursive=True)
    else:
        raise TypeError(
            "'content' argument need to be a dictionary or a list but found,"
            f" '{type(content)}"
        )
    return result
