"""Module with types definitions."""

from pydantic import BeforeValidator
from typing_extensions import Annotated

from . import utils as ut

SliceQuery = Annotated[slice, BeforeValidator(ut.dict_to_slice)]
TimeComboDict = Annotated[dict, BeforeValidator(ut.assert_time_combo_dict)]
BoundingBoxDict = Annotated[dict, BeforeValidator(ut.assert_bounding_box_dict)]
