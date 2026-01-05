""" HomeKit Charging Plug Accessory """
from __future__ import annotations
from typing import TYPE_CHECKING

import threading

import logging

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_SENSOR

from carconnectivity.charging_connector import ChargingConnector
from carconnectivity.observable import Observable
from carconnectivity.vehicle import ElectricVehicle

from carconnectivity_plugins.homekit.accessories.generic_accessory import GenericAccessory

if TYPE_CHECKING:
    from typing import Optional, Any

    from pyhap.service import Service
    from pyhap.accessory_driver import AccessoryDriver

    from carconnectivity.vehicle import GenericVehicle

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge


LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.charging_plug")


class ChargingPlugAccessory(GenericAccessory):
    """Charging Plug Accessory"""
    category: int = CATEGORY_SENSOR

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 vehicle: GenericVehicle) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str)
        self.vehicle: GenericVehicle = vehicle

        # pyright: ignore[reportArgumentType]
        self.service: Optional[Service] = self.add_preload_service(service='ContactSensor',  # pyright: ignore[reportArgumentType]
                                                                   chars=['Name', 'ConfiguredName',  # pyright: ignore[reportArgumentType]
                                                                          'ContactSensorState', 'StatusFault'])

        self.char_contact_sensor_state: Optional[Characteristic] = None
        self.cc_connection_state_lock: threading.Lock = threading.Lock()

        self.add_name_characteristics()
        self.add_status_fault_characteristic()

        if self.vehicle is not None and isinstance(self.vehicle, ElectricVehicle) and self.vehicle.charging is not None \
                and self.vehicle.charging.connector is not None:
            if self.vehicle.charging.connector.connection_state is not None and self.vehicle.charging.connector.connection_state.enabled:
                self.vehicle.charging.connector.connection_state.add_observer(self.__on_cc_connection_state_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
                self.char_contact_sensor_state = self.service.configure_char('ContactSensorState')
                self.__on_cc_connection_state_change(self.vehicle.charging.connector.connection_state, Observable.ObserverEvent.VALUE_CHANGED)

    def __on_cc_connection_state_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_connection_state_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED:
                if self.char_contact_sensor_state is not None:
                    if element.value is None:
                        self.char_contact_sensor_state.set_value(0)
                        if self.char_status_fault is not None:
                            self.char_status_fault.set_value(0)
                    if isinstance(element.value, ChargingConnector.ChargingConnectorConnectionState):
                        if element.value == ChargingConnector.ChargingConnectorConnectionState.CONNECTED:
                            self.char_contact_sensor_state.set_value(0)
                            if self.char_status_fault is not None:
                                self.char_status_fault.set_value(0)
                        elif element.value in [ChargingConnector.ChargingConnectorConnectionState.DISCONNECTED,
                                               ChargingConnector.ChargingConnectorConnectionState.UNSUPPORTED]:
                            self.char_contact_sensor_state.set_value(1)
                            if self.char_status_fault is not None:
                                self.char_status_fault.set_value(0)
                        else:
                            self.char_contact_sensor_state.set_value(1)
                            if self.char_status_fault is not None:
                                self.char_status_fault.set_value(1)
                else:
                    LOG.debug('Unsupported event %s', flags)
