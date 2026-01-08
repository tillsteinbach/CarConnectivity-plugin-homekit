""" HomeKit Climatization Accessory """
from __future__ import annotations
from typing import TYPE_CHECKING

import logging
import threading
from datetime import datetime, timezone

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_AIR_CONDITIONER

from carconnectivity.errors import SetterError
from carconnectivity.commands import GenericCommand
from carconnectivity.observable import Observable
from carconnectivity.vehicle import ElectricVehicle
from carconnectivity.units import Temperature
from carconnectivity.attributes import TemperatureAttribute
from carconnectivity.climatization import Climatization
from carconnectivity.command_impl import ClimatizationStartStopCommand

from carconnectivity_plugins.homekit.accessories.generic_accessory import BatteryGenericVehicleAccessory
from carconnectivity_plugins.homekit.accessories.util import TEMPERATURE_UNIT_TO_VALUE, VALUE_TO_TEMPERATURE_UNIT

if TYPE_CHECKING:
    from typing import Optional, Any, Dict

    from pyhap.service import Service
    from pyhap.accessory_driver import AccessoryDriver

    from carconnectivity.vehicle import GenericVehicle

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge

LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.climatization")


class ClimatizationAccessory(BatteryGenericVehicleAccessory):  # pylint: disable=too-many-instance-attributes
    """Climatization Accessory"""

    category: int = CATEGORY_AIR_CONDITIONER

    # pylint: disable=duplicate-code
    # pylint: disable-next=too-many-arguments,too-many-positional-arguments,too-many-branches,too-many-statements
    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 vehicle: GenericVehicle) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str, vehicle=vehicle)

        self.update_remaining_duration_timer: Optional[threading.Timer] = None

        # pyright: ignore[reportArgumentType]
        self.service: Optional[Service] = self.add_preload_service(service='Thermostat',  # pyright: ignore[reportArgumentType]
                                                                   chars=['Name', 'ConfiguredName',  # pyright: ignore[reportArgumentType]
                                                                          'CurrentHeatingCoolingState', 'TargetHeatingCoolingState',
                                                                          'TargetTemperature', 'TemperatureDisplayUnits',
                                                                          'RemainingDuration', 'StatusFault'])

        self.char_target_heating_cooling_state: Optional[Characteristic] = None
        self.char_current_heating_cooling_state: Optional[Characteristic] = None
        self.char_target_temperature: Optional[Characteristic] = None
        self.char_temperature_display_units: Optional[Characteristic] = None
        self.char_remaining_duration: Optional[Characteristic] = None
        self.estimated_date_reached: Optional[datetime] = None

        self.cc_car_type_lock: threading.Lock = threading.Lock()
        self.cc_climatization_state_lock: threading.Lock = threading.Lock()
        self.cc_estimated_date_reached_lock: threading.Lock = threading.Lock()
        self.cc_target_temperature_lock: threading.Lock = threading.Lock()

        self.target_temperature_attribute: Optional[TemperatureAttribute] = None
        self.climatization_start_stop_command: Optional[GenericCommand] = None
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
        self.current_target_temperature: Optional[float] = None
        if self.vehicle is not None and self.vehicle.climatization is not None \
                and (target_temperature_attribute := self.vehicle.climatization.settings.target_temperature) is not None:
            self.target_temperature_attribute = target_temperature_attribute
            target_temperature_attribute.add_observer(self.__on_cc_target_temperature_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
            if target_temperature_attribute.enabled:
                self.current_target_temperature = target_temperature_attribute.temperature_in(unit=self.configured_temperature_unit)
            if self.current_target_temperature is None:
                if self.configured_temperature_unit == Temperature.C:
                    self.current_target_temperature = 16
                elif self.configured_temperature_unit == Temperature.F:
                    self.current_target_temperature = 61
                else:
                    LOG.error('Invalid temperature unit: %s', self.configured_temperature_unit)
            self.char_target_temperature = self.service.configure_char('TargetTemperature', value=self.current_target_temperature,
                                                                       setter_callback=self.__on_hk_target_temperature_change)
            self.__update_display_units_properties()

        if self.vehicle is not None and self.vehicle.climatization is not None:
            if self.vehicle.climatization.state is not None:
                self.vehicle.climatization.state.add_observer(self.__on_cc_climatization_state_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
                self.char_current_heating_cooling_state = self.service.configure_char('CurrentHeatingCoolingState')
                if self.vehicle.climatization.state.enabled:
                    self.__on_cc_climatization_state_change(self.vehicle.climatization.state, Observable.ObserverEvent.VALUE_CHANGED)
                else:
                    self.__on_cc_climatization_state_change(Climatization.ClimatizationState.UNKNOWN, Observable.ObserverEvent.VALUE_CHANGED)

            if self.vehicle.climatization.commands is not None and self.vehicle.climatization.commands.contains_command('start-stop'):
                self.climatization_start_stop_command = self.vehicle.climatization.commands.commands['start-stop']
                self.char_target_heating_cooling_state = self.service.configure_char('TargetHeatingCoolingState',
                                                                                     valid_values={'Auto': 3, 'Off': 0},
                                                                                     setter_callback=self.__on_hk_target_heating_cooling_state_changed)
                self.char_target_heating_cooling_state.allow_invalid_client_values = True
                # call on change again to also set the target state
                self.__on_cc_climatization_state_change(self.vehicle.climatization.state, Observable.ObserverEvent.VALUE_CHANGED)

            if self.vehicle.climatization.estimated_date_reached is not None:
                self.vehicle.climatization.estimated_date_reached.add_observer(self.__on_cc_estimated_date_reached_change,
                                                                               flag=Observable.ObserverEvent.UPDATED_NEW_MEASUREMENT)
                self.char_remaining_duration = self.service.configure_char('RemainingDuration')
                if self.vehicle.climatization.estimated_date_reached.enabled:
                    self.__on_cc_estimated_date_reached_change(self.vehicle.climatization.estimated_date_reached,
                                                               Observable.ObserverEvent.UPDATED_NEW_MEASUREMENT)

        self.add_name_characteristics()
        self.add_status_fault_characteristic()

        if self.battery_service is None and isinstance(self.vehicle, ElectricVehicle):
            self.add_soc_characteristic()
        else:
            self.vehicle.add_observer(self.__on_cc_car_type_change, flag=Observable.ObserverEvent.UPDATED)
    # pylint: disable=duplicate-code

    def __on_cc_car_type_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_car_type_lock:
            if flags & Observable.ObserverEvent.UPDATED:
                if isinstance(element, ElectricVehicle):
                    self.add_soc_characteristic()
                    self.vehicle.type.remove_observer(self.__on_cc_car_type_change)
            else:
                LOG.debug('Unsupported event %s', flags)

    def __on_cc_target_temperature_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_target_temperature_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED and isinstance(element, TemperatureAttribute):
                target_temperature_unit: Temperature = Temperature.C
                if self.char_temperature_display_units is not None:
                    target_temperature_unit = VALUE_TO_TEMPERATURE_UNIT[self.char_temperature_display_units.get_value()]
                if self.char_target_temperature is not None and element.enabled and element.value is not None:
                    self.char_target_temperature.set_value(element.temperature_in(unit=target_temperature_unit))
                LOG.info('targetTemperature Changed: %f', element.temperature_in(unit=target_temperature_unit))
            else:
                LOG.debug('Unsupported event %s', flags)

    def __on_hk_target_temperature_change(self, value: int) -> None:
        if self.char_target_temperature is not None:
            if self.target_temperature_attribute is not None and self.target_temperature_attribute.enabled:
                self.current_target_temperature = value
                if self.configured_temperature_unit is None:
                    unit: Temperature = Temperature.C
                else:
                    unit = self.configured_temperature_unit
                self.target_temperature_attribute.set_value(value=value, unit=unit)
                LOG.info('targetTemperature Changed: %f', value)
            else:
                LOG.error('Target temperature attribute not available')
        else:
            LOG.error('Target temperature characteristic not available')

    def __on_hk_target_heating_cooling_state_changed(self, value: int) -> None:
        try:
            if self.climatization_start_stop_command is not None and self.climatization_start_stop_command.enabled:
                if value in (1, 2, 3):
                    LOG.info('Switch climatization on')
                    command_args: Dict[str, Any] = {}
                    command_args['command'] = ClimatizationStartStopCommand.Command.START
                    self.climatization_start_stop_command.value = command_args
                elif value == 0:
                    LOG.info('Switch climatization off')
                    command_args: Dict[str, Any] = {}
                    command_args['command'] = ClimatizationStartStopCommand.Command.STOP
                    self.climatization_start_stop_command.value = command_args
                else:
                    LOG.error('Input for climatization not understood: %d', value)
        except SetterError as setter_error:
            LOG.error('Error starting climatization: %s', setter_error)
            if self.char_current_heating_cooling_state is not None and self.char_target_heating_cooling_state is not None \
                    and self.char_current_heating_cooling_state.value in [1, 2]:
                self.char_target_heating_cooling_state.set_value(3)
            elif self.char_target_heating_cooling_state is not None:
                self.char_target_heating_cooling_state.set_value(0)
            self.set_status_fault(1, timeout=120)

    def __on_hk_temperature_display_units_change(self, value: int) -> None:
        if value in VALUE_TO_TEMPERATURE_UNIT:
            if self.char_temperature_display_units is not None:
                self.char_temperature_display_units.set_value(value)
            self.bridge.set_config_item(self.id_str, self.vin, 'TemperatureDisplayUnits', value)
            self.configured_temperature_unit = VALUE_TO_TEMPERATURE_UNIT[value]
            self.__update_display_units_properties()
            self.__on_cc_target_temperature_change(element=self.target_temperature_attribute, flags=Observable.ObserverEvent.VALUE_CHANGED)
        else:
            LOG.error('Invalid temperature display unit: %d', value)

    def __update_display_units_properties(self) -> None:
        if self.char_target_temperature is not None and self.char_temperature_display_units is not None:
            min_step: float = 0.5
            if self.target_temperature_attribute is not None and self.target_temperature_attribute.precision is not None:
                min_step = self.target_temperature_attribute.precision
            if self.configured_temperature_unit == Temperature.C:
                max_value: float = 29.5
                if self.target_temperature_attribute is not None and self.target_temperature_attribute.maximum is not None:
                    max_value = self.target_temperature_attribute.maximum
                min_value: float = 16
                if self.target_temperature_attribute is not None and self.target_temperature_attribute.minimum is not None:
                    min_value = self.target_temperature_attribute.minimum
                self.char_target_temperature.override_properties(properties={'maxValue': max_value, 'minStep': min_step, 'minValue': min_value})
            elif self.configured_temperature_unit == Temperature.F:
                max_value: float = 85
                if self.target_temperature_attribute is not None and self.target_temperature_attribute.maximum is not None:
                    max_value = self.target_temperature_attribute.maximum
                min_value: float = 61
                if self.target_temperature_attribute is not None and self.target_temperature_attribute.minimum is not None:
                    min_value = self.target_temperature_attribute.minimum
                self.char_target_temperature.override_properties(properties={'maxValue': 85, 'minStep': min_step, 'minValue': 61})

    def __on_cc_climatization_state_change(self, element: Any, flags: Observable.ObserverEvent) -> None:  # pylint: disable=too-many-branches
        with self.cc_climatization_state_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED:
                if self.char_current_heating_cooling_state is not None:
                    if element.value is None:
                        self.char_current_heating_cooling_state.set_value(0)
                        if self.char_target_heating_cooling_state is not None:
                            self.char_target_heating_cooling_state.set_value(0)
                    elif element.value == Climatization.ClimatizationState.HEATING:
                        self.char_current_heating_cooling_state.set_value(1)
                        if self.char_target_heating_cooling_state is not None:
                            self.char_target_heating_cooling_state.set_value(3)
                    elif element.value in (Climatization.ClimatizationState.COOLING, Climatization.ClimatizationState.VENTILATION):
                        self.char_current_heating_cooling_state.set_value(2)
                        if self.char_target_heating_cooling_state is not None:
                            self.char_target_heating_cooling_state.set_value(3)
                    elif element.value == Climatization.ClimatizationState.OFF:
                        self.char_current_heating_cooling_state.set_value(0)
                        if self.char_target_heating_cooling_state is not None:
                            self.char_target_heating_cooling_state.set_value(0)
                    else:
                        self.char_current_heating_cooling_state.set_value(0)
                        if self.char_target_heating_cooling_state is not None:
                            self.char_target_heating_cooling_state.set_value(0)
                        LOG.warning('unsupported climatisationState: %s', element.value.value)
                    LOG.debug('Climatization State Changed: %s', element.value.value)
                else:
                    LOG.debug('Unsupported event %s', flags)

    def __on_cc_estimated_date_reached_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_estimated_date_reached_lock:
            if flags & Observable.ObserverEvent.UPDATED_NEW_MEASUREMENT:
                if self.char_remaining_duration is not None:
                    if element.enabled and element.value is not None and isinstance(element.value, datetime):
                        self.estimated_date_reached = element.value
                        self.__update_remaining_duration()
                        LOG.debug('Climatization estimated date reached Changed: %s', self.estimated_date_reached.isoformat())
                    else:
                        self.estimated_date_reached = None
                        self.char_remaining_duration.set_value(0)
                        LOG.debug('Climatization estimated date reached Changed: None')
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
