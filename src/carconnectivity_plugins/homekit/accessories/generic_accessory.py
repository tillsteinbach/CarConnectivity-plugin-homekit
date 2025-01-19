""" This module defines the GenericAccessory class. """
from __future__ import annotations
from typing import TYPE_CHECKING

import logging
import threading

from pyhap.accessory import Accessory
from pyhap.characteristic import Characteristic

from carconnectivity.observable import Observable
from carconnectivity.vehicle import ElectricVehicle
from carconnectivity.charging import Charging

if TYPE_CHECKING:
    from typing import Optional, Any

    from pyhap.accessory_driver import AccessoryDriver
    from pyhap.service import Service

    from carconnectivity.vehicle import GenericVehicle, ElectricDrive

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge

LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.generic_accessory")


class GenericAccessory(Accessory):
    """
    GenericAccessory is a class that represents a generic accessory in a HomeKit environment.

    Attributes:
        driver (AccessoryDriver): The driver for the accessory.
        bridge (CarConnectivityBridge): The bridge for car connectivity.
        id_str (str): The identifier string for the accessory.
        vin (str): The vehicle identification number.
        display_name (str): The display name of the accessory.
        service (Optional[Service]): The service associated with the accessory.
        char_status_fault (Optional[Characteristic]): The characteristic for status fault.
        char_configured_name (Optional[Characteristic]): The characteristic for configured name.
        char_name (Optional[Characteristic]): The characteristic for name.
    """
    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str) -> None:
        super().__init__(driver=driver, display_name=display_name, aid=aid)

        self.driver: AccessoryDriver = driver
        self.bridge: CarConnectivityBridge = bridge
        self.id_str: str = id_str
        self.vin: str = vin

        self.service: Optional[Service] = None

        self.char_status_fault: Optional[Characteristic] = None
        self.__char_status_fault_timer: Optional[threading.Timer] = None

        self.char_configured_name: Optional[Characteristic] = None
        self.char_name: Optional[Characteristic] = None

    def add_name_characteristics(self) -> None:
        """
        Adds name characteristics to the accessory's service.

        This method retrieves the configured name for the accessory from the bridge configuration.
        If no configured name is found, it defaults to the display name of the accessory.
        It then configures the 'ConfiguredName' and 'Name' characteristics for the accessory's service.

        Returns:
            None
        """
        configured_name: Optional[str] = self.bridge.get_config_item(self.id_str, self.vin, 'ConfiguredName')
        if configured_name is None:
            configured_name: Optional[str] = self.display_name
        if self.service is not None:
            self.char_configured_name: Optional[Characteristic] = self.service.configure_char(char_name='ConfiguredName', value=configured_name,
                                                                                              setter_callback=self.__on_configured_name_changed)
            self.char_name: Optional[Characteristic] = self.service.configure_char(char_name='Name', value=configured_name)

    def __on_configured_name_changed(self, value: Any) -> None:
        """
        Callback function that is triggered when the configured name changes.

        This function updates the configuration and persists it when the configured name changes.
        It also updates the characteristic values for `char_configured_name` and `char_name` if they are not None.

        Args:
            value (Any): The new configured name value.
        """
        if value is not None and len(value) > 0:
            self.bridge.set_config_item(id_str=self.id_str, vin=self.vin, config_key='ConfiguredName', item=value)
            self.bridge.persist_config()
            if self.char_configured_name is not None:
                self.char_configured_name.set_value(value)
            if self.char_name is not None:
                self.char_name.set_value(value)

    def add_status_fault_characteristic(self) -> None:
        """
        Adds a 'StatusFault' characteristic to the accessory's service.

        This method checks if the accessory's service is not None and then
        configures a 'StatusFault' characteristic with an initial value of 0.

        Returns:
            None
        """
        if self.service is not None:
            self.char_status_fault = self.service.configure_char(char_name='StatusFault', value=0)

    def set_status_fault(self, value, timeout: float = 0, timeout_value: Optional[int] = None) -> None:
        """
        Sets the status fault characteristic to the given value. If a timeout is specified, the status fault will be reset
        to the timeout_value after the timeout period.

        Args:
            value: The value to set for the status fault characteristic.
            timeout (float, optional): The time in seconds after which the status fault should be reset. Defaults to 0.
            timeout_value (Optional[int], optional): The value to reset the status fault to after the timeout. If not
                                                     specified, the current value of the status fault characteristic will
                                                     be used. Defaults to None.

        Returns:
            None
        """
        if self.char_status_fault is not None:
            if self.__char_status_fault_timer is not None and self.__char_status_fault_timer.is_alive():
                self.__char_status_fault_timer.cancel()
                self.__char_status_fault_timer = None
            if timeout == 0:
                self.char_status_fault.set_value(value)
            else:
                if timeout_value is None:
                    timeout_value = self.char_status_fault.get_value()
                self.char_status_fault.set_value(value)
                self.__char_status_fault_timer = threading.Timer(timeout, self.__reset_status_fault, [timeout_value])
                self.__char_status_fault_timer.daemon = True
                self.__char_status_fault_timer.start()

    def __reset_status_fault(self, value: int) -> None:
        """
        Resets the status fault characteristic to the given value.

        Args:
            value (int): The value to set for the status fault characteristic.

        Returns:
            None
        """
        if self.char_status_fault is not None:
            self.char_status_fault.set_value(value)


class BatteryGenericVehicleAccessory(GenericAccessory):
    """Vehcile Accessory with battery characteristics"""

    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 vehicle: GenericVehicle) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str)

        self.vehicle: GenericVehicle = vehicle

        self.battery_service: Optional[Service] = None
        self.char_battery_level: Optional[Characteristic] = None
        self.char_status_low_battery: Optional[Characteristic] = None
        self.char_charging_state: Optional[Characteristic] = None

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

    def add_soc_characteristic(self) -> None:
        """
        Adds the State of Charge (SoC) characteristic to the accessory if the vehicle is an electric vehicle.

        This method checks if the vehicle is an instance of `ElectricVehicle`. If so, it retrieves the electric drive
        and its level. If the level is enabled, it adds an observer to monitor changes in the level value. It then
        adds a battery service with characteristics for battery level, low battery status, and charging state.
        The battery level and low battery status are configured and set based on the current level value of the
        electric drive. If the accessory has a service, the battery service is linked to it.

        Returns:
            None
        """
        if isinstance(self.vehicle, ElectricVehicle):
            electric_drive: ElectricDrive = self.vehicle.get_electric_drive()
            if electric_drive is not None and electric_drive.level is not None and electric_drive.level.enabled:
                electric_drive.level.add_observer(self._on_level_change, Observable.ObserverEvent.VALUE_CHANGED)
                self.battery_service: Optional[Service] = self.add_preload_service(service='BatteryService',  # pyright: ignore[reportArgumentType]
                                                                                   chars=['BatteryLevel',  # pyright: ignore[reportArgumentType]
                                                                                          'StatusLowBattery',
                                                                                          'ChargingState'])
                self.char_battery_level = self.battery_service.configure_char('BatteryLevel')
                self.char_battery_level.set_value(electric_drive.level.value)
                self.char_status_low_battery = self.battery_service.configure_char('StatusLowBattery')
                self._set_low_battery_status(electric_drive.level.value)
                if self.service is not None:
                    self.service.add_linked_service(self.battery_service)
                if self.vehicle.charging is not None and self.vehicle.charging.state is not None and self.vehicle.charging.state.enabled:
                    self.vehicle.charging.state.add_observer(self._on_charging_state, Observable.ObserverEvent.VALUE_CHANGED)
                    self.char_charging_state = self.battery_service.configure_char('ChargingState')
                    self._set_charging_state(self.vehicle.charging.state.value)

    def _set_low_battery_status(self, level: Optional[float]) -> None:
        if self.char_status_low_battery is not None:
            if level is None or level > 10:
                self.char_status_low_battery.set_value(0)
            else:
                self.char_status_low_battery.set_value(1)

    def _set_charging_state(self, charging_state) -> None:
        if self.char_charging_state is not None:
            if charging_state is not None:
                if charging_state in (Charging.ChargingState.OFF,
                                      Charging.ChargingState.READY_FOR_CHARGING,
                                      Charging.ChargingState.UNSUPPORTED):
                    self.char_charging_state.set_value(0)
                elif charging_state in (Charging.ChargingState.CHARGING,
                                        Charging.ChargingState.DISCHARGING,
                                        Charging.ChargingState.CONSERVATION):
                    self.char_charging_state.set_value(1)
                elif charging_state == Charging.ChargingState.ERROR:
                    self.char_charging_state.set_value(2)
                else:
                    self.char_charging_state.set_value(2)
                    LOG.warning('unsupported charging state: %s', charging_state)
            else:
                self.char_charging_state.set_value(2)

    def _on_level_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        if flags & Observable.ObserverEvent.VALUE_CHANGED:
            if element.value is not None and self.char_battery_level is not None:
                self.char_battery_level.set_value(element.value)
                self._set_low_battery_status(element.value)

    def _on_charging_state(self, element: Any, flags: Observable.ObserverEvent) -> None:
        if flags & Observable.ObserverEvent.VALUE_CHANGED:
            if element.value is not None and self.char_charging_state is not None:
                self._set_charging_state(element.value)
