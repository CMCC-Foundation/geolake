"""Geokube Plugin for Intake."""

# This avoids a circular dependency pitfall by ensuring that the
# driver-discovery code runs first, see:
# https://intake.readthedocs.io/en/latest/making-plugins.html#entrypoints
from .queries.geoquery import GeoQuery
