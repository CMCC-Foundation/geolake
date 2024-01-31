"""Geokube Plugin for Intake."""

# This avoids a circilar dependency pitfall by ensuring that the
# driver-discovery code runs first, see:
# https://intake.readthedocs.io/en/latest/making-plugins.html#entrypoints
from .geoquery import GeoQuery