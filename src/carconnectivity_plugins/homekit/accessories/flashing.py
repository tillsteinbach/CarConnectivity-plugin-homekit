""" HomeKit Flashing Light Accessory """
from __future__ import annotations
from typing import TYPE_CHECKING

import logging
from threading import Timer

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_LIGHTBULB

from carconnectivity.commands import GenericCommand
from carconnectivity.errors import SetterError
from carconnectivity.command_impl import HonkAndFlashCommand

from carconnectivity_plugins.homekit.accessories.generic_accessory import GenericAccessory

if TYPE_CHECKING:
    from typing import Optional, Any, Dict

    from pyhap.service import Service
    from pyhap.accessory_driver import AccessoryDriver

    from carconnectivity.vehicle import GenericVehicle

    from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge


LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.charging_plug")


class FlashingLightAccessory(GenericAccessory):
    """Flashing Light Accessory"""
    category: int = CATEGORY_LIGHTBULB

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(self, driver: AccessoryDriver, bridge: CarConnectivityBridge, aid: int, id_str: str, vin: str, display_name: str,
                 vehicle: GenericVehicle) -> None:
        super().__init__(driver=driver, bridge=bridge, display_name=display_name, aid=aid, vin=vin, id_str=id_str)
        self.vehicle: GenericVehicle = vehicle

        # pyright: ignore[reportArgumentType]
        self.service: Optional[Service] = self.add_preload_service(service='Lightbulb',  # pyright: ignore[reportArgumentType]
                                                                   chars=['Name', 'ConfiguredName',  # pyright: ignore[reportArgumentType]
                                                                          'On', 'StatusFault'])

        self.char_on: Optional[Characteristic] = None

        self.add_name_characteristics()
        self.add_status_fault_characteristic()

        if self.vehicle is not None and self.vehicle.commands is not None and self.vehicle.commands.commands is not None \
                and 'honk-flash' in self.vehicle.commands.commands:
            self.honk_flash_command: GenericCommand = self.vehicle.commands.commands['honk-flash']
            self.char_on = self.service.configure_char('On', setter_callback=self.__on_hk_on_change)

    def __on_hk_on_change(self, value: Any) -> None:
        try:
            if self.honk_flash_command is not None and self.honk_flash_command.enabled:
                if value is True:
                    LOG.info('Start flashing for 10 seconds')
                    command_args: Dict[str, Any] = {}
                    command_args['command'] = HonkAndFlashCommand.Command.FLASH
                    self.honk_flash_command.value = command_args

                    def reset_state():
                        if self.char_on is not None:
                            self.char_on.set_value(False)

                    timer = Timer(10.0, reset_state)
                    timer.start()
                else:
                    LOG.error('Flashing cannot be turned off, please wait for flashing to stop')
        except SetterError as setter_error:
            LOG.error('Error honk and flash: %s', setter_error)
            if self.char_on is not None:
                self.char_on.set_value(False)
            self.set_status_fault(1, timeout=120)
