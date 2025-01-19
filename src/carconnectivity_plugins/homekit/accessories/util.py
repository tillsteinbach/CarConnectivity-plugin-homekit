""" Utility functions and constants for HomeKit accessories. """
from __future__ import annotations
from typing import TYPE_CHECKING

from carconnectivity.units import Temperature

if TYPE_CHECKING:
    from typing import Dict

TEMPERATURE_UNIT_TO_VALUE: Dict[Temperature, int] = {Temperature.C: 0, Temperature.F: 1}
VALUE_TO_TEMPERATURE_UNIT: Dict[int, Temperature] = {0: Temperature.C, 1: Temperature.F}
