"""Per-product capability metadata and query enforcement.

A product's intake-catalog ``metadata.capabilities`` block declares which
operations a client may request for that product (spatial / temporal / vertical
subsetting, output formats, regridding, temporal resampling) and which
presentation hints the web portal should apply (raw variable labels).

The same model is consumed by:

* the API (``api/app/endpoint_handlers/dataset.py``) to reject a ``GeoQuery``
  that uses a disabled / disallowed operation, and
* the web portal (``web/app/widget.py``) to build only the widgets a product
  actually supports.

Every field is optional in the catalog; an absent block (or an absent key)
falls back to a default that reproduces the historical behavior, so products
without a ``capabilities`` block are unchanged.
"""
from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from geoquery.geoquery import GeoQuery

_LOG = logging.getLogger("geokube.capabilities")

# --- Option registries (value -> display metadata) -----------------------
# These relocate the option lists/labels previously hardcoded in the web
# ``WidgetFactory``. The web builds widget option lists from them; the API uses
# the allowed *values* to validate a query.

FORMAT_REGISTRY: dict[str, dict[str, str]] = {
    "netcdf": {"label": "netCDF", "ext": ".nc"},
    "geojson": {"label": "GeoJSON", "ext": ".json"},
    "zarr": {"label": "Zarr", "ext": ".zarr"},
}

GRID_REGISTRY: dict[str, str] = {
    "native": "Native",
    "regular": "Regular",
}

RESAMPLE_FREQ_REGISTRY: dict[str, str] = {
    "1D": "Daily",
    "1ME": "Monthly",
    "1Y": "Yearly",
}

RESAMPLE_OP_REGISTRY: dict[str, str] = {
    "mean": "Mean",
    "max": "Max",
    "min": "Min",
    "sum": "Sum",
    "median": "Median",
}

# Default exposed format(s). Kept to netCDF only to reproduce today's behavior
# for products that do not declare a ``format`` capability.
DEFAULT_FORMATS: list[str] = ["netcdf"]


class FormatCapability(BaseModel):
    """Output formats a product may be requested in."""

    model_config = ConfigDict(extra="ignore")

    values: list[str] = Field(default_factory=lambda: list(DEFAULT_FORMATS))


class RegridCapability(BaseModel):
    """Whether (and to which grids) a product may be regridded."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    values: list[str] = Field(default_factory=lambda: list(GRID_REGISTRY))


class ResampleCapability(BaseModel):
    """Whether (and with which frequencies/operators) a product may be
    temporally resampled."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    frequencies: list[str] = Field(
        default_factory=lambda: list(RESAMPLE_FREQ_REGISTRY)
    )
    operators: list[str] = Field(
        default_factory=lambda: list(RESAMPLE_OP_REGISTRY)
    )


class DatasetCapabilities(BaseModel):
    """The set of operations allowed for a product.

    Defaults reproduce the historical behavior: every kind of subsetting is
    allowed, only netCDF output is offered, and neither regridding nor temporal
    resampling is available.
    """

    model_config = ConfigDict(extra="ignore")

    temporal_subset: bool = True
    spatial_subset: bool = True
    vertical_subset: bool = True
    # Presentation-only: when True the web portal uses raw field names as
    # variable labels (skipping webmapping and capitalization). This is *not*
    # enforced by ``check`` - it cannot be "violated" by a query.
    variable_raw_labels: bool = False
    format: FormatCapability = Field(default_factory=FormatCapability)
    regrid: RegridCapability = Field(default_factory=RegridCapability)
    resample: ResampleCapability = Field(default_factory=ResampleCapability)

    @classmethod
    def from_metadata(
        cls, metadata: Optional[dict]
    ) -> "DatasetCapabilities":
        """Build from a product's catalog metadata dict.

        Tolerates ``None``, an empty dict, a missing ``capabilities`` key, and a
        malformed block: in every such case it returns all-default capabilities
        (= historical behavior), so an unannotated or misconfigured product can
        never break the (unauthenticated) read/estimate paths with a 500.
        """
        if not metadata:
            return cls()
        caps = metadata.get("capabilities")
        if not caps:
            return cls()
        if not isinstance(caps, dict):
            _LOG.warning(
                "ignoring malformed `capabilities` (expected a mapping, got"
                " %s); falling back to defaults",
                type(caps).__name__,
            )
            return cls()
        try:
            return cls(**caps)
        except ValidationError:
            _LOG.warning(
                "ignoring invalid `capabilities` block; falling back to"
                " defaults",
                exc_info=True,
            )
            return cls()

    def check(self, query: GeoQuery) -> list[str]:
        """Return a list of human-readable violations for ``query``.

        An empty list means the query only uses operations this product
        supports. Pure: never raises and never mutates ``query``.
        """
        violations: list[str] = []

        if not self.spatial_subset and (
            query.area is not None or query.location is not None
        ):
            violations.append(
                "spatial subsetting (area/location) is not supported for this"
                " product"
            )
        if not self.temporal_subset and query.time is not None:
            violations.append(
                "temporal subsetting (time) is not supported for this product"
            )
        if not self.vertical_subset and query.vertical is not None:
            violations.append(
                "vertical subsetting is not supported for this product"
            )

        if query.regrid is not None:
            if not self.regrid.enabled:
                violations.append(
                    "regridding is not supported for this product"
                )
            elif query.regrid not in self.regrid.values:
                violations.append(
                    f"regrid '{query.regrid}' is not allowed for this product"
                    f" (allowed: {', '.join(self.regrid.values)})"
                )

        if query.resample:
            if not self.resample.enabled:
                violations.append(
                    "temporal resampling is not supported for this product"
                )
            else:
                freq = query.resample.get("frequency")
                operator = query.resample.get("operator")
                if (
                    freq is not None
                    and freq not in self.resample.frequencies
                ):
                    violations.append(
                        f"resample frequency '{freq}' is not allowed for this"
                        f" product (allowed:"
                        f" {', '.join(self.resample.frequencies)})"
                    )
                if (
                    operator is not None
                    and operator not in self.resample.operators
                ):
                    violations.append(
                        f"resample operator '{operator}' is not allowed for"
                        f" this product (allowed:"
                        f" {', '.join(self.resample.operators)})"
                    )

        if (
            query.format is not None
            and query.format not in self.format.values
        ):
            violations.append(
                f"format '{query.format}' is not allowed for this product"
                f" (allowed: {', '.join(self.format.values)})"
            )

        return violations
