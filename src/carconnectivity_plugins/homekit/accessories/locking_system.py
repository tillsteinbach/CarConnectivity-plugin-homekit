""" HomeKit Locking Accessory """
from __future__ import annotations
from typing import TYPE_CHECKING

import threading

import logging

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_DOOR_LOCK

from carconnectivity.errors import SetterError
from carconnectivity.attributes import Observable
from carconnectivity.commands import GenericCommand
from carconnectivity.command_impl import LockUnlockCommand
from carconnectivity.doors import Doors

from carconnectivity_plugins.homekit.accessories.generic_accessory import GenericAccessory

if TYPE_CHECKING:
    from typing import Optional, Any, Dict

    from pyhap.service import Service
    from pyhap.accessory_driver import AccessoryDriver

    from carconnectivity.vehicle import GenericVehicle

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge


LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.locking")


class LockingAccessory(GenericAccessory):
    """Flashing Light Accessory"""
    category: int = CATEGORY_DOOR_LOCK

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 vehicle: GenericVehicle) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str)
        self.vehicle: GenericVehicle = vehicle

        # pyright: ignore[reportArgumentType]
        self.service: Optional[Service] = self.add_preload_service(service='LockMechanism',  # pyright: ignore[reportArgumentType]
                                                                   chars=['Name', 'ConfiguredName',  # pyright: ignore[reportArgumentType]
                                                                          'LockCurrentState', 'LockTargetState', 'StatusFault'])

        self.char_lock_current_state: Optional[Characteristic] = None
        self.char_lock_target_state: Optional[Characteristic] = None

        self.cc_lock_state_lock: threading.Lock = threading.Lock()

        self.add_name_characteristics()
        self.add_status_fault_characteristic()

        if self.vehicle is not None and self.vehicle.doors is not None:
            if self.vehicle.doors.commands is not None and self.vehicle.commands.commands is not None \
                    and self.vehicle.doors.commands.contains_command('lock-unlock'):
                self.lock_unlock_command: GenericCommand = self.vehicle.doors.commands.commands['lock-unlock']
                self.char_lock_target_state = self.service.configure_char('LockTargetState', setter_callback=self.__on_hk_lock_target_state_change)
                self.char_lock_target_state.allow_invalid_client_values = True
            if self.vehicle.doors.lock_state is not None and self.vehicle.doors.lock_state.enabled:
                self.vehicle.doors.lock_state.add_observer(self.__on_cc_lock_state_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
                self.char_lock_current_state = self.service.configure_char('LockCurrentState')
                self.__on_cc_lock_state_change(self.vehicle.doors.lock_state, flags=Observable.ObserverEvent.VALUE_CHANGED)

    def __on_hk_lock_target_state_change(self, value: Any) -> None:
        if self.char_lock_target_state is not None:
            if self.lock_unlock_command is not None and self.lock_unlock_command.enabled:
                command_args: Dict[str, Any] = {}
                try:
                    if value == 1:
                        LOG.info('Lock car')
                        command_args['command'] = LockUnlockCommand.Command.LOCK
                        self.lock_unlock_command.value = command_args
                    elif value == 0:
                        LOG.info('Unlock car')
                        command_args['command'] = LockUnlockCommand.Command.UNLOCK
                        self.lock_unlock_command.value = command_args
                    else:
                        LOG.error('Input for lock target not understood: %d', value)
                        self.set_status_fault(1, timeout=120)
                except SetterError as setter_error:
                    LOG.error('Error locking or unlocking: %s', setter_error)
                    if self.char_lock_current_state is not None and self.char_lock_current_state.value in [1, 3]:
                        self.char_lock_target_state.set_value(1)
                    else:
                        self.char_lock_target_state.set_value(0)
                    self.set_status_fault(1, timeout=120)
            else:
                LOG.error('Locking cannot be controlled')
                if self.char_lock_current_state is not None and self.char_lock_current_state.value in [1, 3]:
                    self.char_lock_target_state.set_value(1)
                else:
                    self.char_lock_target_state.set_value(0)
                self.set_status_fault(1, timeout=120)

    def __on_cc_lock_state_change(self, element: Any, flags: Observable.ObserverEvent) -> None:
        with self.cc_lock_state_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED:
                if self.char_lock_current_state is not None:
                    if element.value == Doors.LockState.LOCKED:
                        self.char_lock_current_state.set_value(1)
                        if self.char_lock_target_state is not None:
                            self.char_lock_target_state.set_value(1)
                    elif element.value == Doors.LockState.UNLOCKED:
                        self.char_lock_current_state.set_value(0)
                        if self.char_lock_target_state is not None:
                            self.char_lock_target_state.set_value(0)
                    elif element.value == Doors.LockState.INVALID:
                        self.char_lock_current_state.set_value(3)
                        if self.char_lock_target_state is not None:
                            self.char_lock_target_state.set_value(1)
                    elif element.value == Doors.LockState.UNKNOWN:
                        self.char_lock_current_state.set_value(3)
                        if self.char_lock_target_state is not None:
                            self.char_lock_target_state.set_value(1)
                    else:
                        self.char_lock_current_state.set_value(3)
                        if self.char_lock_target_state is not None:
                            self.char_lock_target_state.set_value(1)
                        LOG.warning('unsupported lock state: %s', element.value)
