"""Module implements the plugin to connect with Homekit"""
from __future__ import annotations
from typing import TYPE_CHECKING

import os
import re
import threading
import logging
from pathlib import Path

from pyhap.accessory_driver import AccessoryDriver

from carconnectivity.errors import ConfigurationError
from carconnectivity.util import config_remove_credentials
from carconnectivity_plugins.base.plugin import BasePlugin
from carconnectivity_plugins.homekit._version import __version__

from carconnectivity_plugins.homekit.accessories.custom_characteristics import CUSTOM_CHARACTERISTICS
from carconnectivity_plugins.homekit.accessories.bridge import CarConnectivityBridge

if TYPE_CHECKING:
    from typing import Dict, Optional
    from carconnectivity.carconnectivity import CarConnectivity

LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit")


class Plugin(BasePlugin):
    """
    Plugin class for HomeKit integration.
    Args:
        car_connectivity (CarConnectivity): An instance of CarConnectivity.
        config (Dict): Configuration dictionary containing connection details.
    """
    def __init__(self, plugin_id: str, car_connectivity: CarConnectivity, config: Dict) -> None:  # pylint: disable=too-many-branches, too-many-statements
        BasePlugin.__init__(self, plugin_id=plugin_id, car_connectivity=car_connectivity, config=config, log=LOG)

        self._background_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        LOG.info("Loading homekit plugin with config %s", config_remove_credentials(config))

        if 'address' in config and config['address'] is not None:
            self.active_config['address'] = config['address']
        else:
            self.active_config['address'] = None

        if 'port' in config and config['port'] is not None:
            self.active_config['port'] = config['port']
            if self.active_config['port'] > 65535 or self.active_config['port'] < 1:
                raise ConfigurationError(f'Invalid port: "{self.active_config["port"]}" not in range 1-65535')
        else:
            self.active_config['port'] = 51234

        if 'pincode' in config and config['pincode'] is not None:
            pincode: Optional[str] = config['pincode']
            if pincode is not None and not re.match(pattern=r'^\d{3}-\d{2}-\d{3}$', string=pincode):
                raise ConfigurationError(f'Invalid pincode format: "{pincode}". Expected format is "xxx-xx-xxx" where x is a digit.')
        else:
            pincode = None

        if 'accessory_state_file' in config and config['accessory_state_file'] is not None:
            self.active_config['accessory_state_file'] = os.path.expanduser(config['accessory_state_file'])
        else:
            self.active_config['accessory_state_file'] = os.path.expanduser('~/.carconnectivity/homekit-accessory.state')
        file = Path(self.active_config['accessory_state_file'])
        file.parent.mkdir(parents=True, exist_ok=True)

        if 'accessory_config_file' in config and config['accessory_config_file'] is not None:
            self.active_config['accessory_config_file'] = os.path.expanduser(config['accessory_config_file'])
        else:
            self.active_config['accessory_config_file'] = os.path.expanduser('~/.carconnectivity/homekit-accessory.config')
        file = Path(self.active_config['accessory_config_file'])
        file.parent.mkdir(parents=True, exist_ok=True)

        if 'ignore_vins' in config and config['ignore_vins'] is not None:
            self.active_config['ignore_vins'] = config['ignore_vins']
        else:
            self.active_config['ignore_vins'] = []

        if 'ignore_accessory_types' in config and config['ignore_accessory_types'] is not None:
            self.active_config['ignore_accessory_types'] = config['ignore_accessory_types']
        else:
            self.active_config['ignore_accessory_types'] = []

        # Add the accessory driver
        self._driver = AccessoryDriver(address=self.active_config['address'], port=self.active_config['port'], pincode=pincode,
                                       persist_file=self.active_config['accessory_state_file'])

        for characteristic_key, characteristic in CUSTOM_CHARACTERISTICS.items():
            self._driver.loader.char_types[characteristic_key] = characteristic

        self._bridge = CarConnectivityBridge(driver=self._driver, car_connectivity=car_connectivity,
                                             accessory_config_file=self.active_config['accessory_config_file'],
                                             ignore_vins=self.active_config['ignore_vins'], ignore_accessory_types=self.active_config['ignore_accessory_types'])
        self._driver.add_accessory(self._bridge)

    def startup(self) -> None:
        LOG.info("Starting Homekit plugin")
        self._background_thread = threading.Thread(target=self._driver.start, daemon=False)
        self._background_thread.name = 'carconnectivity.plugins.homekit-background'
        self._background_thread.start()
        update_thread = threading.Timer(interval=5.0, function=self.__delayed_update)
        update_thread.daemon = True
        update_thread.start()
        self.healthy._set_value(value=True)  # pylint: disable=protected-access
        LOG.debug("Starting Homekit plugin done")

    def __delayed_update(self) -> None:
        self.stop_event.wait(5.0)
        if not self.stop_event.is_set():
            self._bridge.install_observers()
            if self.car_connectivity.garage is not None:
                for vehicle in self.car_connectivity.garage.list_vehicles():
                    self._bridge.update(vehicle=vehicle)

    def shutdown(self) -> None:
        self.stop_event.set()
        self._driver.stop()
        if self._background_thread is not None:
            self._background_thread.join()
        return super().shutdown()

    def get_version(self) -> str:
        return __version__

    def get_type(self) -> str:
        """
        Returns the type of the plugin.

        :return: A string representing the type of the plugin.
        """
        return "carconnectivity-plugin-homekit"

    def get_name(self) -> str:
        return "HomeKit Plugin"
