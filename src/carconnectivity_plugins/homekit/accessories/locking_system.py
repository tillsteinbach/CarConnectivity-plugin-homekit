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
from carconnectivity.attributes import EnumAttribute

from carconnectivity_plugins.homekit.accessories.generic_accessory import GenericAccessory

if TYPE_CHECKING:
    from typing import Optional, Any, Dict

    from pyhap.service import Service
    from pyhap.accessory_driver import AccessoryDriver

    from carconnectivity.vehicle import GenericVehicle

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge


LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.locking")


class LockingAccessory(GenericAccessory):
    """Locking Accessory"""
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
        # None if the connector does not offer a lock-unlock command; the lock is then read-only
        self.lock_unlock_command: Optional[GenericCommand] = None

        self.cc_lock_state_lock: threading.Lock = threading.Lock()

        self.add_name_characteristics()
        self.add_status_fault_characteristic()

        if self.vehicle is not None and self.vehicle.doors is not None:
            if self.vehicle.doors.commands is not None and self.vehicle.doors.commands.commands is not None \
                    and self.vehicle.doors.commands.contains_command('lock-unlock'):
                self.lock_unlock_command = self.vehicle.doors.commands.commands['lock-unlock']
            # LockTargetState is a required, writable characteristic of LockMechanism, so HomeKit can always write to it.
            # The setter is therefore registered in any case: without a command it only logs and resets the target state.
            self.char_lock_target_state = self.service.configure_char('LockTargetState', setter_callback=self.__on_hk_lock_target_state_change)
            self.char_lock_target_state.allow_invalid_client_values = True
            if self.vehicle.doors.lock_state is not None:
                self.vehicle.doors.lock_state.add_observer(self.__on_cc_lock_state_change, flag=Observable.ObserverEvent.VALUE_CHANGED)
                self.char_lock_current_state = self.service.configure_char('LockCurrentState')
                if self.vehicle.doors.lock_state.enabled:
                    self.__on_cc_lock_state_change(self.vehicle.doors.lock_state, flags=Observable.ObserverEvent.VALUE_CHANGED)
                else:
                    self.__on_cc_lock_state_change(None, flags=Observable.ObserverEvent.VALUE_CHANGED)

    def __del__(self) -> None:
        if self.vehicle is not None and self.vehicle.doors is not None:
            if self.vehicle.doors.lock_state is not None:
                self.vehicle.doors.lock_state.remove_observer(self.__on_cc_lock_state_change)

    def __reset_hk_lock_target_state(self) -> None:
        """Set LockTargetState back to the current lock state so the Home app does not stay in 'Locking…'/'Unlocking…'."""
        if self.char_lock_target_state is not None:
            if self.char_lock_current_state is not None and self.char_lock_current_state.value in [1, 3]:
                self.char_lock_target_state.set_value(1)
            else:
                self.char_lock_target_state.set_value(0)

    def __on_hk_lock_target_state_change(self, value: Any) -> None:
        if self.char_lock_target_state is None:
            return
        if self.lock_unlock_command is None:
            # Read-only lock: the connector only reports the lock state but cannot lock or unlock the vehicle
            LOG.warning('%s: Lock target state change to %s requested from HomeKit, but locking cannot be controlled with this connector '
                        '(read-only lock state). Ignoring request.', self.display_name, value)
            self.__reset_hk_lock_target_state()
            self.set_status_fault(1, timeout=120)
            return
        if not self.lock_unlock_command.enabled:
            LOG.error('Locking cannot be controlled')
            self.__reset_hk_lock_target_state()
            self.set_status_fault(1, timeout=120)
            return
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
            self.__reset_hk_lock_target_state()
            self.set_status_fault(1, timeout=120)

    # pylint: disable-next=too-many-branches
    def __on_cc_lock_state_change(self, element: Optional[EnumAttribute[Doors.LockState]], flags: Observable.ObserverEvent) -> None:
        with self.cc_lock_state_lock:
            if flags & Observable.ObserverEvent.VALUE_CHANGED:
                if self.char_lock_current_state is not None:
                    if element is None or element.value is None:
                        self.char_lock_current_state.set_value(3)
                        if self.char_lock_target_state is not None:
                            self.char_lock_target_state.set_value(1)
                    elif element.value == Doors.LockState.LOCKED:
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
