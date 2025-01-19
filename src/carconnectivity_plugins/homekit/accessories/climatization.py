""" HomeKit Climatization Accessory """
from __future__ import annotations
from typing import TYPE_CHECKING

import logging

from pyhap.accessory_driver import AccessoryDriver
from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_AIR_CONDITIONER

from carconnectivity_plugins.homekit.accessories.generic_accessory import GenericAccessory

if TYPE_CHECKING:
    from carconnectivity.climatization import Climatization

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge

LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.climatization")


class ClimatizationAccessory(GenericAccessory):
    """Climatization Accessory"""

    category: int = CATEGORY_AIR_CONDITIONER

    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 climatization: Climatization) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str)

        self.climatization: Climatization = climatization
        # pyright: ignore[reportArgumentType]
        self.service = self.add_preload_service(service='Thermostat',  # pyright: ignore[reportArgumentType]
                                                chars=['Name', 'ConfiguredName', 'CurrentHeatingCoolingState',  # pyright: ignore[reportArgumentType]
                                                        'TargetHeatingCoolingState', 'TargetTemperature', 'TemperatureDisplayUnits',
                                                        'RemainingDuration', 'StatusFault'])
        self.battery_service = self.add_preload_service(service='BatteryService',  # pyright: ignore[reportArgumentType]
                                                        chars=['BatteryLevel', 'StatusLowBattery',  # pyright: ignore[reportArgumentType]
                                                               'ChargingState'])
        self.service.add_linked_service(self.battery_service)

        self.char_target_temperature: Characteristic = self.service.configure_char('TargetTemperature', value=16,
                                                                                   properties={'maxValue': 29.5, 'minStep': 0.5, 'minValue': 16})  #,
                                                                                   #setter_callback=self.__onTargetTemperatureChanged)

        # if batteryStatus is not None and batteryStatus.currentSOC_pct.enabled:
        #     batteryStatus.currentSOC_pct.addObserver(self.onCurrentSOCChange, AddressableLeaf.ObserverEvent.VALUE_CHANGED)
        #     self.charBatteryLevel = self.batteryService.configure_char('BatteryLevel')
        #     self.charBatteryLevel.set_value(batteryStatus.currentSOC_pct.value)
        #     self.charStatusLowBattery = self.batteryService.configure_char('StatusLowBattery')
        #     self.setStatusLowBattery(batteryStatus.currentSOC_pct)

        # if batteryStatus is not None and chargingStatus is not None and chargingStatus.chargingState.enabled:
        #     chargingStatus.chargingState.addObserver(self.onChargingState, AddressableLeaf.ObserverEvent.VALUE_CHANGED)
        #     self.charChargingState = self.batteryService.configure_char('ChargingState')
        #     self.setChargingState(chargingStatus.chargingState)

        # Set constant to celsius
        # TODO: We can enable conversion here later
        self.char_temperature_display_units: Characteristic = self.service.configure_char('TemperatureDisplayUnits')
        self.char_temperature_display_units.set_value(0)

        self.add_name_characteristics()
        self.add_status_fault_characteristic()
