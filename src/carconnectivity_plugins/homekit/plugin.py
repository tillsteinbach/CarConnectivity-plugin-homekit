"""Module implements the plugin to connect with ABRP"""
from __future__ import annotations
from typing import TYPE_CHECKING

import time
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
    def __init__(self, plugin_id: str, car_connectivity: CarConnectivity, config: Dict) -> None:
        BasePlugin.__init__(self, plugin_id=plugin_id, car_connectivity=car_connectivity, config=config)

        self._background_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Configure logging
        if 'log_level' in config and config['log_level'] is not None:
            config['log_level'] = config['log_level'].upper()
            if config['log_level'] in logging._nameToLevel:
                LOG.setLevel(config['log_level'])
                self.log_level._set_value(config['log_level'])  # pylint: disable=protected-access
            else:
                raise ConfigurationError(f'Invalid log level: "{config["log_level"]}" not in {list(logging._nameToLevel.keys())}')
        LOG.info("Loading homekit plugin with config %s", config_remove_credentials(self.config))

        if 'address' in config and config['address'] is not None:
            address: Optional[str] = config['address']
        else:
            address = None

        if 'port' in config and config['port'] is not None:
            port: int = config['port']
            if port > 65535 or port < 1:
                raise ConfigurationError(f'Invalid port: "{port}" not in range 1-65535')
        else:
            port = 51234

        if 'pincode' in config and config['pincode'] is not None:
            pincode: Optional[str] = config['pincode']
            if pincode is not None and not re.match(pattern=r'^\d{3}-\d{2}-\d{3}$', string=pincode):
                raise ConfigurationError(f'Invalid pincode format: "{pincode}". Expected format is "xxx-xx-xxx" where x is a digit.')
        else:
            pincode = None

        if 'accessory_state_file' in config and config['accessory_state_file'] is not None:
            accessory_state_file: str = os.path.expanduser(config['accessory_state_file'])
        else:
            accessory_state_file: str = os.path.expanduser('~/.carconnectivity/homekit-accessory.state')
        file = Path(accessory_state_file)
        file.parent.mkdir(parents=True, exist_ok=True)

        if 'accessory_config_file' in config and config['accessory_config_file'] is not None:
            accessory_config_file: str = os.path.expanduser(config['accessory_config_file'])
        else:
            accessory_config_file: str = os.path.expanduser('~/.carconnectivity/homekit-accessory.config')
        file = Path(accessory_config_file)
        file.parent.mkdir(parents=True, exist_ok=True)

        # Add the accessory driver
        self._driver = AccessoryDriver(address=address, port=port, pincode=pincode, persist_file=accessory_state_file)

        for characteristic_key, characteristic in CUSTOM_CHARACTERISTICS.items():
            self._driver.loader.char_types[characteristic_key] = characteristic

        self._bridge = CarConnectivityBridge(driver=self._driver, car_connectivity=car_connectivity, accessory_config_file=accessory_config_file)
        self._driver.add_accessory(self._bridge)

    def startup(self) -> None:
        LOG.info("Starting Homekit plugin")
        self._background_thread = threading.Thread(target=self.__delayed_startup, daemon=False)
        self._background_thread.start()
        LOG.debug("Starting Homekit plugin done")

    def __delayed_startup(self) -> None:
        self._driver.start()

    def shutdown(self) -> None:
        self._driver.stop()
        if self._background_thread is not None:
            self._background_thread.join()
        return super().shutdown()

    def get_version(self) -> str:
        return __version__
