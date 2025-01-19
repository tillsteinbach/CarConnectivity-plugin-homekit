""" This module defines the GenericAccessory class. """
from __future__ import annotations
from typing import TYPE_CHECKING

import threading

from pyhap.accessory import Accessory
from pyhap.characteristic import Characteristic

if TYPE_CHECKING:
    from typing import Optional, Any

    from pyhap.accessory_driver import AccessoryDriver
    from pyhap.service import Service

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge


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
