""" HomeKit Outside Temperature Accessory """
from __future__ import annotations
from typing import TYPE_CHECKING

import logging

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_SENSOR

from carconnectivity.observable import Observable
from carconnectivity.attributes import TemperatureAttribute, Temperature

from carconnectivity_plugins.homekit.accessories.generic_accessory import GenericAccessory
from carconnectivity_plugins.homekit.accessories.util import VALUE_TO_TEMPERATURE_UNIT, TEMPERATURE_UNIT_TO_VALUE

if TYPE_CHECKING:
    from typing import Optional, Any

    from pyhap.service import Service
    from pyhap.accessory_driver import AccessoryDriver

    from carconnectivity.vehicle import GenericVehicle

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge


LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.outside_temperature")


class OutsideTemperatureAccessory(GenericAccessory):
    """Outside Temperature Accessory"""
    category: int = CATEGORY_SENSOR

    # pylint: disable=duplicate-code
    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 vehicle: GenericVehicle) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str)
        self.vehicle: GenericVehicle = vehicle

        # pyright: ignore[reportArgumentType]
        self.service: Optional[Service] = self.add_preload_service(service='TemperatureSensor',  # pyright: ignore[reportArgumentType]
                                                                   chars=['Name', 'ConfiguredName',  # pyright: ignore[reportArgumentType]
                                                                          'TemperatureDisplayUnits', 'CurrentTemperature'])

        self.char_current_temperature: Optional[Characteristic] = None
        self.char_temperature_display_units: Optional[Characteristic] = None

        self.outside_temperature_attribute: Optional[TemperatureAttribute] = None

        self.add_name_characteristics()

        temperature_display_unit: Optional[int] = self.bridge.get_config_item(self.id_str, self.vin, 'TemperatureDisplayUnits')
        if temperature_display_unit is None:
            temperature_display_unit = TEMPERATURE_UNIT_TO_VALUE[Temperature.C]
            self.configured_temperature_unit: Temperature = Temperature.C
        else:
            self.configured_temperature_unit: Temperature = VALUE_TO_TEMPERATURE_UNIT[temperature_display_unit]
        if self.service is not None:
            self.char_temperature_display_units = self.service.configure_char('TemperatureDisplayUnits', value=temperature_display_unit,
                                                                              valid_values={"Celsius": 0, "Fahrenheit": 1},
                                                                              setter_callback=self.__on_hk_temperature_display_units_change)

        if self.vehicle is not None and vehicle.outside_temperature is not None and vehicle.outside_temperature.enabled:
            self.outside_temperature_attribute = self.vehicle.outside_temperature
            self.vehicle.outside_temperature.add_observer(self.__on_cc_outside_temperature_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
            self.char_current_temperature = self.service.configure_char('CurrentTemperature')
            self.__on_cc_outside_temperature_change(self.vehicle.outside_temperature, Observable.ObserverEvent.VALUE_CHANGED)
    # pylint: disable=duplicate-code

    def __on_cc_outside_temperature_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        if flags & Observable.ObserverEvent.VALUE_CHANGED and isinstance(element, TemperatureAttribute):
            target_temperature_unit: Temperature = Temperature.C
            if self.char_temperature_display_units is not None:
                target_temperature_unit = VALUE_TO_TEMPERATURE_UNIT[self.char_temperature_display_units.get_value()]
            if self.char_current_temperature is not None and element.enabled and element.value is not None:
                self.char_current_temperature.set_value(element.temperature_in(unit=target_temperature_unit))
            LOG.info('targetTemperature Changed: %f', element.temperature_in(unit=target_temperature_unit))
        else:
            LOG.debug('Unsupported event %s', flags)

    def __on_hk_temperature_display_units_change(self, value: int) -> None:
        if value in VALUE_TO_TEMPERATURE_UNIT:
            if self.char_temperature_display_units is not None:
                self.char_temperature_display_units.set_value(value)
            self.bridge.set_config_item(self.id_str, self.vin, 'TemperatureDisplayUnits', value)
            self.configured_temperature_unit = VALUE_TO_TEMPERATURE_UNIT[value]
            if self.outside_temperature_attribute is not None:
                self.__on_cc_outside_temperature_change(element=self.outside_temperature_attribute, flags=Observable.ObserverEvent.VALUE_CHANGED)
        else:
            LOG.error('Invalid temperature display unit: %d', value)
