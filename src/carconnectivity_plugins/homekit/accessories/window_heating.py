""" HomeKit WindowHeating Accessory """
from __future__ import annotations
from typing import TYPE_CHECKING

import threading

import logging


from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_SWITCH

from carconnectivity.errors import SetterError
from carconnectivity.commands import GenericCommand
from carconnectivity.command_impl import WindowHeatingStartStopCommand
from carconnectivity.observable import Observable
from carconnectivity.window_heating import WindowHeatings

from carconnectivity_plugins.homekit.accessories.generic_accessory import GenericAccessory

if TYPE_CHECKING:
    from typing import Optional, Any, Dict

    from pyhap.service import Service
    from pyhap.accessory_driver import AccessoryDriver

    from carconnectivity.vehicle import GenericVehicle

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge


LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.window_heating")


class WindowHeatingAccessory(GenericAccessory):  # pylint: disable=too-many-instance-attributes
    """Window heating Accessory"""

    category: int = CATEGORY_SWITCH

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 vehicle: GenericVehicle) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str)
        self.vehicle: GenericVehicle = vehicle

        # pyright: ignore[reportArgumentType]
        self.service: Optional[Service] = self.add_preload_service(service='Switch',  # pyright: ignore[reportArgumentType]
                                                                   chars=['Name', 'ConfiguredName',  # pyright: ignore[reportArgumentType]
                                                                          'On', 'StatusFault'])

        self.char_on: Optional[Characteristic] = None

        self.window_heating_start_stop_command: Optional[GenericCommand] = None

        self.cc_heating_state_lock: threading.Lock = threading.Lock()

        self.add_name_characteristics()
        self.add_status_fault_characteristic()

        if self.vehicle is not None and self.vehicle.window_heatings is not None:
            if self.vehicle.window_heatings.heating_state is not None and self.vehicle.window_heatings.heating_state.enabled:
                self.vehicle.window_heatings.heating_state.add_observer(self.__on_cc_heating_state_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
                self.char_on = self.service.configure_char('On', setter_callback=self.__on_hk_on_change)
                self.__on_cc_heating_state_change(self.vehicle.window_heatings.heating_state, Observable.ObserverEvent.VALUE_CHANGED)
                if self.vehicle.window_heatings.commands is not None and self.vehicle.window_heatings.commands.contains_command('start-stop'):
                    self.window_heating_start_stop_command = self.vehicle.window_heatings.commands.commands['start-stop']

    def __on_cc_heating_state_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_heating_state_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED:
                if self.char_on is not None:
                    if element.value is None:
                        self.char_on.set_value(0)
                    elif element.value == WindowHeatings.HeatingState.OFF:
                        self.char_on.set_value(0)
                    elif element.value == WindowHeatings.HeatingState.ON:
                        self.char_on.set_value(1)
                    elif element.value in (WindowHeatings.HeatingState.INVALID,
                                           WindowHeatings.HeatingState.UNSUPPORTED,
                                           WindowHeatings.HeatingState.UNKNOWN):
                        self.char_on.set_value(0)
                    else:
                        self.char_on.set_value(0)
                        LOG.warning('unsupported Window Heating state: %s', element.value.value)
            else:
                LOG.debug('Unsupported event %s', flags)

    def __on_hk_on_change(self, value: Any) -> None:
        try:
            if self.window_heating_start_stop_command is not None and self.window_heating_start_stop_command.enabled:
                if value in [1, 2, 3]:
                    LOG.info('Switch window heating ging on')
                    command_args: Dict[str, Any] = {}
                    command_args['command'] = WindowHeatingStartStopCommand.Command.START
                    self.window_heating_start_stop_command.value = command_args
                elif value == 0:
                    LOG.info('Switch window heating off')
                    command_args: Dict[str, Any] = {}
                    command_args['command'] = WindowHeatingStartStopCommand.Command.STOP
                    self.window_heating_start_stop_command.value = command_args
                else:
                    LOG.error('Input for window heating not understood: %d', value)
        except SetterError as setter_error:
            LOG.error('Error starting/stopping window heating: %s', setter_error)
            self.set_status_fault(1, timeout=120)
