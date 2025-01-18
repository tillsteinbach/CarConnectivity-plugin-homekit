"""Module implements the plugin to connect with ABRP"""
from __future__ import annotations
from typing import TYPE_CHECKING

import threading
import logging

from carconnectivity.errors import ConfigurationError
from carconnectivity.util import config_remove_credentials
from carconnectivity_plugins.base.plugin import BasePlugin
from carconnectivity_plugins.abrp._version import __version__

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

    def startup(self) -> None:
        LOG.info("Starting Homekit plugin")
        self._background_thread = threading.Thread(target=self._background_loop, daemon=False)
        self._background_thread.start()
        LOG.debug("Starting Homekit plugin done")

    def _background_loop(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            self._stop_event.wait(60)

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._background_thread is not None:
            self._background_thread.join()
        return super().shutdown()

    def get_version(self) -> str:
        return __version__
