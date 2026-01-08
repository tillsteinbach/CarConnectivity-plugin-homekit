""" HomeKit Charging Accessory """
from __future__ import annotations
from typing import TYPE_CHECKING

import threading
from datetime import datetime, timezone
import logging


from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_OUTLET

from carconnectivity.errors import SetterError
from carconnectivity.commands import GenericCommand
from carconnectivity.command_impl import ChargingStartStopCommand
from carconnectivity.charging_connector import ChargingConnector
from carconnectivity.observable import Observable
from carconnectivity.vehicle import ElectricVehicle
from carconnectivity.charging import Charging
from carconnectivity.attributes import PowerAttribute
from carconnectivity.units import Power

from carconnectivity_plugins.homekit.accessories.generic_accessory import BatteryGenericVehicleAccessory

if TYPE_CHECKING:
    from typing import Optional, Any, Dict

    from pyhap.service import Service
    from pyhap.accessory_driver import AccessoryDriver

    from carconnectivity.vehicle import GenericVehicle

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge


LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.charging")


class ChargingAccessory(BatteryGenericVehicleAccessory):  # pylint: disable=too-many-instance-attributes
    """Charging Accessory"""

    category: int = CATEGORY_OUTLET

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 vehicle: GenericVehicle) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str, vehicle=vehicle)

        self.update_remaining_duration_timer: Optional[threading.Timer] = None

        # pyright: ignore[reportArgumentType]
        self.service: Optional[Service] = self.add_preload_service(service='Outlet',  # pyright: ignore[reportArgumentType]
                                                                   chars=['Name', 'ConfiguredName',  # pyright: ignore[reportArgumentType]
                                                                          'On', 'OutletInUse', 'RemainingDuration', 'Consumption', 'StatusFault'])

        self.char_on: Optional[Characteristic] = None
        self.char_remaining_duration: Optional[Characteristic] = None
        self.char_consumption: Optional[Characteristic] = None
        self.char_outlet_in_use: Optional[Characteristic] = None

        self.charging_start_stop_command: Optional[GenericCommand] = None

        self.cc_charging_state_lock: threading.Lock = threading.Lock()
        self.cc_date_reached_lock: threading.Lock = threading.Lock()
        self.cc_power_lock: threading.Lock = threading.Lock()
        self.cc_connector_state_lock: threading.Lock = threading.Lock()

        self.add_name_characteristics()
        self.add_status_fault_characteristic()
        self.add_soc_characteristic()

        if self.vehicle is not None and isinstance(self.vehicle, ElectricVehicle) and self.vehicle.charging is not None:
            if self.vehicle.charging.state is not None:
                self.vehicle.charging.state.add_observer(self.__on_cc_charging_state_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
                self.char_on = self.service.configure_char('On', setter_callback=self.__on_hk_on_change)
                if self.vehicle.charging.state.enabled:
                    self.__on_cc_charging_state_change(self.vehicle.charging.state, Observable.ObserverEvent.VALUE_CHANGED)
                else:
                    self.__on_cc_charging_state_change(Charging.ChargingState.UNKNOWN, Observable.ObserverEvent.VALUE_CHANGED)

                if self.vehicle.charging.commands is not None and self.vehicle.charging.commands.contains_command('start-stop'):
                    self.charging_start_stop_command = self.vehicle.charging.commands.commands['start-stop']

            if self.vehicle.charging.estimated_date_reached is not None:
                self.vehicle.charging.estimated_date_reached.add_observer(self.__on_cc_estimated_date_reached_change,
                                                                          flag=Observable.ObserverEvent.UPDATED_NEW_MEASUREMENT)
                self.char_remaining_duration = self.service.configure_char('RemainingDuration')
                if self.vehicle.charging.estimated_date_reached.enabled:
                    self.__on_cc_estimated_date_reached_change(self.vehicle.charging.estimated_date_reached,
                                                               Observable.ObserverEvent.UPDATED_NEW_MEASUREMENT)

            if self.vehicle.charging.power is not None:
                self.vehicle.charging.power.add_observer(self.__on_cc_power_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
                self.char_consumption = self.service.configure_char('Consumption')
                if self.vehicle.charging.power.enabled:
                    self.__on_cc_power_change(self.vehicle.charging.power, Observable.ObserverEvent.VALUE_CHANGED)

            if self.vehicle.charging.connector is not None and self.vehicle.charging.connector.connection_state is not None:
                self.vehicle.charging.connector.connection_state.add_observer(self.__on_cc_connector_state_change,
                                                                              flag=Observable.ObserverEvent.VALUE_CHANGED)
                self.char_outlet_in_use = self.service.configure_char('OutletInUse')
                if self.vehicle.charging.connector.connection_state.enabled:
                    self.__on_cc_connector_state_change(self.vehicle.charging.connector.connection_state,
                                                        Observable.ObserverEvent.VALUE_CHANGED)
                else:
                    self.__on_cc_connector_state_change(ChargingConnector.ChargingConnectorConnectionState.UNKNOWN,
                                                        Observable.ObserverEvent.VALUE_CHANGED)

    def __on_cc_charging_state_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_charging_state_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED:
                if self.char_on is not None:
                    if element.value is None:
                        self.char_on.set_value(0)
                    elif element.value in (Charging.ChargingState.OFF,
                                           Charging.ChargingState.READY_FOR_CHARGING):
                        self.char_on.set_value(0)
                    elif element.value in (Charging.ChargingState.CHARGING,
                                           Charging.ChargingState.DISCHARGING,
                                           Charging.ChargingState.CONSERVATION):
                        self.char_on.set_value(1)
                    elif element.value in (Charging.ChargingState.ERROR,
                                           Charging.ChargingState.UNSUPPORTED):
                        self.char_on.set_value(0)
                    else:
                        self.char_on.set_value(0)
                        LOG.warning('unsupported chargingState: %s', element.value.value)
            else:
                LOG.debug('Unsupported event %s', flags)

    def __on_hk_on_change(self, value: Any) -> None:
        try:
            if self.charging_start_stop_command is not None and self.charging_start_stop_command.enabled:
                if value in [1, 2, 3]:
                    LOG.info('Switch charging on')
                    command_args: Dict[str, Any] = {}
                    command_args['command'] = ChargingStartStopCommand.Command.START
                    self.charging_start_stop_command.value = command_args
                elif value == 0:
                    LOG.info('Switch charging off')
                    command_args: Dict[str, Any] = {}
                    command_args['command'] = ChargingStartStopCommand.Command.STOP
                    self.charging_start_stop_command.value = command_args
                else:
                    LOG.error('Input for charging not understood: %d', value)
        except SetterError as setter_error:
            LOG.error('Error starting/stopping charging: %s', setter_error)
            self.set_status_fault(1, timeout=120)

    def __on_cc_estimated_date_reached_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_date_reached_lock:
            if flags & Observable.ObserverEvent.UPDATED_NEW_MEASUREMENT:
                if self.char_remaining_duration is not None:
                    if element.enabled and element.value is not None and isinstance(element.value, datetime):
                        self.estimated_date_reached = element.value
                        self.__update_remaining_duration()
                        LOG.debug('Charging estimated date reached Changed: %s', self.estimated_date_reached.isoformat())
                    else:
                        self.estimated_date_reached = None
                        self.char_remaining_duration.set_value(0)
                        LOG.debug('Charging estimated date reached Changed: None')
            else:
                LOG.debug('Unsupported event %s', flags)

    # pylint: disable=duplicate-code
    def __update_remaining_duration(self) -> None:
        if self.update_remaining_duration_timer is not None:
            self.update_remaining_duration_timer.cancel()
            self.update_remaining_duration_timer = None
        if self.char_remaining_duration is not None:
            remaining_duration: int = 0
            utc_now: datetime = datetime.now(tz=timezone.utc)
            if self.estimated_date_reached is not None and self.estimated_date_reached > utc_now:
                remaining_duration = round((self.estimated_date_reached - utc_now).total_seconds())
            self.char_remaining_duration.set_value(remaining_duration)
            if remaining_duration > 0 and not self.driver.stop_event.is_set():
                self.update_remaining_duration_timer = threading.Timer(interval=5.0, function=self.__update_remaining_duration)
                self.update_remaining_duration_timer.start()
    # pylint: enable=duplicate-code

    def __on_cc_power_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_power_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED:
                if self.char_consumption is not None:
                    if isinstance(element, PowerAttribute) and element.value is not None:
                        self.char_consumption.set_value(element.power_in(unit=Power.W))
                        LOG.debug('Charging power Changed: %dW', element.power_in(unit=Power.W))
                    else:
                        self.char_consumption.set_value(0)
            else:
                LOG.debug('Unsupported event %s', flags)

    def __on_cc_connector_state_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_connector_state_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED:
                if self.char_outlet_in_use is not None:
                    if element.value is None:
                        self.char_outlet_in_use.set_value(False)
                    elif element.value == ChargingConnector.ChargingConnectorConnectionState.CONNECTED:
                        self.char_outlet_in_use.set_value(True)
                    elif element.value in (ChargingConnector.ChargingConnectorConnectionState.DISCONNECTED,
                                           ChargingConnector.ChargingConnectorConnectionState.INVALID,
                                           ChargingConnector.ChargingConnectorConnectionState.UNSUPPORTED):
                        self.char_outlet_in_use.set_value(False)
                    else:
                        self.char_outlet_in_use.set_value(False)
                        LOG.warning('unsupported charging connector state: %s', element.value.value)
            else:
                LOG.debug('Unsupported event %s', flags)
