""" HomeKit Bridge for CarConnectivity """
from __future__ import annotations
from typing import TYPE_CHECKING

import logging
import json

from pyhap.accessory import Bridge
from pyhap.accessory_driver import AccessoryDriver

from carconnectivity.observable import Observable
from carconnectivity.vehicle import GenericVehicle, ElectricVehicle
from carconnectivity._version import __version__ as __carconnectivity_version__

from carconnectivity_plugins.homekit.accessories.dummy_accessory import DummyAccessory
from carconnectivity_plugins.homekit.accessories.climatization import ClimatizationAccessory
from carconnectivity_plugins.homekit.accessories.charging import ChargingAccessory
from carconnectivity_plugins.homekit.accessories.charging_plug import ChargingPlugAccessory
from carconnectivity_plugins.homekit.accessories.outside_temperature import OutsideTemperatureAccessory
from carconnectivity_plugins.homekit.accessories.flashing import FlashingLightAccessory
from carconnectivity_plugins.homekit.accessories.locking_system import LockingAccessory
from carconnectivity_plugins.homekit._version import __version__


if TYPE_CHECKING:
    from typing import Optional, Any, Dict, List

    from carconnectivity.carconnectivity import CarConnectivity

LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.bridge")


class CarConnectivityBridge(Bridge):
    """VWsfriend Bridge"""

    # pylint: disable-next=too-many-arguments
    def __init__(self, car_connectivity: CarConnectivity, driver: AccessoryDriver, display_name: str = 'CarConnectivity',
                 accessory_config_file: str = '~/.carconnectivity/homekit-accessory.config', ignore_vins: Optional[List[str]] = None,
                 ignore_accessory_types: Optional[List[str]] = None) -> None:
        super().__init__(driver=driver, display_name=display_name, )

        self.set_info_service(f'{__carconnectivity_version__} (HomeKit Plugin {__version__})', 'Till Steinbach', 'CarConnectivity', None)

        self.car_connectivity: CarConnectivity = car_connectivity
        self.ignore_vins: List[str] = ignore_vins or []
        self.ignore_accessory_types: List[str] = ignore_accessory_types or []

        self.driver: AccessoryDriver = driver

        self.accessory_config_file: str = accessory_config_file
        self.__accessory_config: Dict[str, Dict[str, Any]] = {}
        self.next_aid: int = 100
        try:
            self.read_config()
        except FileNotFoundError:
            pass

        for identifier, accessory in self.__accessory_config.items():
            if 'ConfiguredName' in accessory:
                display_name = accessory['ConfiguredName']
            else:
                display_name = identifier
            placeholder_accessory = DummyAccessory(driver=driver, display_name=display_name, aid=accessory['aid'])
            if 'category' in accessory:
                placeholder_accessory.category = accessory['category']
            if 'services' in accessory:
                for service in accessory['services']:
                    placeholder_accessory.add_preload_service(service, chars=None)
            self.add_accessory(placeholder_accessory)

    def install_observers(self) -> None:
        """
        Installs observers for the car connectivity components.

        This method checks if the garage component of the car connectivity is not None.
        If it is not None, it adds an observer to the garage component to listen for updates.
        The observer is set to trigger on the ENABLED event and will execute at the end of a transaction.

        Returns:
            None
        """
        if self.car_connectivity.garage is not None:
            self.car_connectivity.garage.add_observer(observer=self.__on_garage_update, flag=Observable.ObserverEvent.ENABLED, on_transaction_end=True)

    def __on_garage_update(self, element: Any, flags: Observable.ObserverEvent) -> None:
        """Update the accessories when the garage is updated."""
        if (flags & (Observable.ObserverEvent.ENABLED)) and isinstance(element, GenericVehicle):
            self.update(vehicle=element)

    def persist_config(self) -> None:
        """
        Persist the accessory configuration to a file.

        This method writes the accessory configuration to the file specified by
        `self.accessory_config_file` in JSON format. If the file cannot be written,
        an error message is logged.

        Raises:
            ValueError: If there is an error during the JSON serialization process.
        """
        if self.accessory_config_file:
            try:
                with open(file=self.accessory_config_file, mode='w', encoding='utf8') as file:
                    json.dump(self.__accessory_config, fp=file)
                LOG.info('Writing accessory config file %s', self.accessory_config_file)
            except ValueError as err:
                LOG.info('Could not write homekit accessoryConfigFile %s (%s)', self.accessory_config_file, err)

    def read_config(self):
        """
        Reads the accessory configuration from a JSON file and updates the accessory configuration attribute.

        This method opens the accessory configuration file specified by `self.accessory_config_file`, reads its contents,
        and loads it as a JSON object into `self.__accessory_config`. It also logs the action of reading the configuration file.
        Additionally, it iterates through the accessory configurations and updates `self.next_aid` to ensure it is set to
        one more than the highest 'aid' value found in the configurations.

        Raises:
            FileNotFoundError: If the accessory configuration file does not exist.
            json.JSONDecodeError: If the file contents cannot be decoded as JSON.
        """
        with open(file=self.accessory_config_file, mode='r', encoding='utf8') as file:
            self.__accessory_config = json.load(fp=file)
            LOG.info('Reading homekit accessory config file %s', self.accessory_config_file)
            # Find the highest aid in the config and adjust next_aid accordingly
            for accessory_config in self.__accessory_config.values():
                if 'aid' in accessory_config and (accessory_config['aid'] + 1) > self.next_aid:
                    self.next_aid = accessory_config['aid'] + 1

    def update(self, vehicle: GenericVehicle):  # noqa: C901 # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        """
        Update the bridge with the given vehicle's information and accessories.

        Args:
            vehicle (GenericVehicle): The vehicle object containing various attributes and statuses.

        This method performs the following steps:
        1. Checks if the vehicle and its VIN are enabled and not None.
        2. Retrieves and sets the vehicle's manufacturer, name, model, and software version.
        3. Updates or adds the following accessories to the bridge if they are enabled and not ignored:
            - ClimatizationAccessory
            - ChargingAccessory (for ElectricVehicle)
            - ChargingPlugAccessory (for ElectricVehicle)
            - OutsideTemperatureAccessory
            - FlashingLightAccessory
            - LockingAccessory
        4. If any configuration changes are made, updates the driver and persists the configuration.

        Note:
            - Accessories are added to the bridge if they are not already known.
            - If an accessory is known but not of the correct type, it is replaced.
            - The method logs debug information and persists configuration changes if any updates are made.
        """
        config_changed = False
        if vehicle.enabled and vehicle.vin.enabled and vehicle.vin.value is not None:
            vin: str = vehicle.vin.value
            if vin in self.ignore_vins:
                LOG.debug('Ignoring vehicle with VIN %s due to configuration', vin)
                return
            if vehicle.manufacturer.enabled and vehicle.manufacturer.value is not None:
                manufacturer: str = vehicle.manufacturer.value
            else:
                manufacturer: str = 'Unknown'
            if vehicle.name.enabled and vehicle.name.value is not None and len(vehicle.name.value) > 0:
                name: str = vehicle.name.value
            else:
                name: str = vin
            if vehicle.model.enabled and vehicle.model.value is not None and len(vehicle.model.value) > 0:
                model: str = vehicle.model.value
            else:
                model: str = 'Unknown'
            if vehicle.software is not None and vehicle.software.enabled and vehicle.software.version is not None and vehicle.software.version.enabled:
                vehicle_software_version: Optional[str] = vehicle.software.version.value
            else:
                vehicle_software_version: Optional[str] = None
            # Climatization
            climatization_aid: Optional[int] = self.get_existing_aid('Climatization', vin)
            # pylint: disable-next=too-many-boolean-expressions
            if 'Climatization' not in self.ignore_accessory_types \
                    and vehicle.climatization is not None and vehicle.climatization.enabled \
                    and (climatization_aid is None
                         or climatization_aid not in self.accessories
                         or not isinstance(self.accessories[climatization_aid], ClimatizationAccessory)):
                climatization_accessory = ClimatizationAccessory(driver=self.driver, bridge=self, aid=self.select_aid('Climatization', vin),
                                                                 id_str='Climatization', vin=vin, display_name=f'{name} Climatization',
                                                                 vehicle=vehicle)
                climatization_accessory.set_info_service(firmware_revision=vehicle_software_version, manufacturer=manufacturer, model=model,
                                                         serial_number=f'{vin}-climatization')
                self.set_config_item(climatization_accessory.id_str, climatization_accessory.vin, 'category', climatization_accessory.category)
                self.set_config_item(climatization_accessory.id_str, climatization_accessory.vin, 'services',
                                     [service.display_name for service in climatization_accessory.services])
                # Add the accessory to the bridge if not known
                if climatization_accessory.aid not in self.accessories:
                    self.add_accessory(climatization_accessory)
                # Replace the accessory if it is known but not of the correct type (was Dummy before)
                else:
                    self.accessories[climatization_accessory.aid] = climatization_accessory
                config_changed = True

            # Charging
            charging_aid: Optional[int] = self.get_existing_aid('Charging', vin)
            # pylint: disable-next=too-many-boolean-expressions
            if 'Charging' not in self.ignore_accessory_types \
                    and isinstance(vehicle, ElectricVehicle) and vehicle.charging is not None and vehicle.charging.enabled \
                    and (charging_aid is None
                         or charging_aid not in self.accessories or not isinstance(self.accessories[charging_aid], ChargingAccessory)):
                charging_accessory = ChargingAccessory(driver=self.driver, bridge=self, aid=self.select_aid('Charging', vin),
                                                       id_str='Charging', vin=vin, display_name=f'{name} Charging', vehicle=vehicle)
                charging_accessory.set_info_service(firmware_revision=vehicle_software_version, manufacturer=manufacturer, model=model,
                                                    serial_number=f'{vin}-charging')
                self.set_config_item(charging_accessory.id_str, charging_accessory.vin, 'category', charging_accessory.category)
                self.set_config_item(charging_accessory.id_str, charging_accessory.vin, 'services',
                                     [service.display_name for service in charging_accessory.services])
                # Add the accessory to the bridge if not known
                if charging_accessory.aid not in self.accessories:
                    self.add_accessory(charging_accessory)
                # Replace the accessory if it is known but not of the correct type (was Dummy before)
                else:
                    self.accessories[charging_accessory.aid] = charging_accessory
                config_changed = True

            # ChargingPlug
            plug_aid: Optional[int] = self.get_existing_aid('ChargingPlug', vin)
            # pylint: disable-next=too-many-boolean-expressions
            if 'ChargingPlug' not in self.ignore_accessory_types \
                    and isinstance(vehicle, ElectricVehicle) and vehicle.charging is not None and vehicle.charging.enabled \
                    and (plug_aid is None or plug_aid not in self.accessories or not isinstance(self.accessories[plug_aid], ChargingPlugAccessory)):
                charging_plug_accessory = ChargingPlugAccessory(driver=self.driver, bridge=self, aid=self.select_aid('ChargingPlug', vin),
                                                                id_str='ChargingPlug', vin=vin, display_name=f'{name} Charging Plug', vehicle=vehicle)
                charging_plug_accessory.set_info_service(firmware_revision=vehicle_software_version, manufacturer=manufacturer, model=model,
                                                         serial_number=f'{vin}-charging-plug')
                self.set_config_item(charging_plug_accessory.id_str, charging_plug_accessory.vin, 'category', charging_plug_accessory.category)
                self.set_config_item(charging_plug_accessory.id_str, charging_plug_accessory.vin, 'services',
                                     [service.display_name for service in charging_plug_accessory.services])
                # Add the accessory to the bridge if not known
                if charging_plug_accessory.aid not in self.accessories:
                    self.add_accessory(charging_plug_accessory)
                # Replace the accessory if it is known but not of the correct type (was Dummy before)
                else:
                    self.accessories[charging_plug_accessory.aid] = charging_plug_accessory
                config_changed = True

            # OutsideTemperature
            outside_temperature_aid: Optional[int] = self.get_existing_aid('OutsideTemperature', vin)
            # pylint: disable-next=too-many-boolean-expressions
            if 'OutsideTemperature' not in self.ignore_accessory_types \
                    and vehicle.outside_temperature is not None and vehicle.outside_temperature.enabled \
                    and (outside_temperature_aid is None
                         or outside_temperature_aid not in self.accessories or not isinstance(self.accessories[outside_temperature_aid],
                                                                                              OutsideTemperatureAccessory)):
                outside_temperature_accessory = OutsideTemperatureAccessory(driver=self.driver, bridge=self, aid=self.select_aid('OutsideTemperature', vin),
                                                                            id_str='OutsideTemperature', vin=vin, display_name=f'{name} Outside Temperature',
                                                                            vehicle=vehicle)
                outside_temperature_accessory.set_info_service(firmware_revision=vehicle_software_version, manufacturer=manufacturer, model=model,
                                                               serial_number=f'{vin}-outside-temperature')
                self.set_config_item(outside_temperature_accessory.id_str, outside_temperature_accessory.vin, 'category',
                                     outside_temperature_accessory.category)
                self.set_config_item(outside_temperature_accessory.id_str, outside_temperature_accessory.vin, 'services',
                                     [service.display_name for service in outside_temperature_accessory.services])
                # Add the accessory to the bridge if not known
                if outside_temperature_accessory.aid not in self.accessories:
                    self.add_accessory(outside_temperature_accessory)
                # Replace the accessory if it is known but not of the correct type (was Dummy before)
                else:
                    self.accessories[outside_temperature_accessory.aid] = outside_temperature_accessory
                config_changed = True

            # FlashingAccessory
            flashing_light_aid: Optional[int] = self.get_existing_aid('FlashingLight', vin)
            # pylint: disable-next=too-many-boolean-expressions
            if 'FlashingLight' not in self.ignore_accessory_types \
                    and vehicle.commands is not None and vehicle.commands is not None and 'honk-flash' in vehicle.commands.commands \
                    and (flashing_light_aid is None or flashing_light_aid not in self.accessories or not isinstance(self.accessories[flashing_light_aid],
                                                                                                                    FlashingLightAccessory)):
                flashing_light_accessory = FlashingLightAccessory(driver=self.driver, bridge=self, aid=self.select_aid('FlashingLight', vin),
                                                                  id_str='FlashingLight', vin=vin, display_name=f'{name} Flashing',
                                                                  vehicle=vehicle)
                flashing_light_accessory.set_info_service(firmware_revision=vehicle_software_version, manufacturer=manufacturer, model=model,
                                                          serial_number=f'{vin}-flashing-light')
                self.set_config_item(flashing_light_accessory.id_str, flashing_light_accessory.vin, 'category',
                                     flashing_light_accessory.category)
                self.set_config_item(flashing_light_accessory.id_str, flashing_light_accessory.vin, 'services',
                                     [service.display_name for service in flashing_light_accessory.services])
                # Add the accessory to the bridge if not known
                if flashing_light_accessory.aid not in self.accessories:
                    self.add_accessory(flashing_light_accessory)
                # Replace the accessory if it is known but not of the correct type (was Dummy before)
                else:
                    self.accessories[flashing_light_accessory.aid] = flashing_light_accessory
                config_changed = True

            # LockingAccessory
            locking_aid: Optional[int] = self.get_existing_aid('Locking', vin)
            # pylint: disable-next=too-many-boolean-expressions
            if 'Locking' not in self.ignore_accessory_types \
                    and vehicle.doors is not None and vehicle.doors.commands is not None \
                    and 'lock-unlock' in vehicle.doors.commands.commands \
                    and (locking_aid is None or locking_aid not in self.accessories or not isinstance(self.accessories[locking_aid],
                                                                                                      LockingAccessory)):
                locking_accessory = LockingAccessory(driver=self.driver, bridge=self, aid=self.select_aid('Locking', vin),
                                                     id_str='Locking', vin=vin, display_name=f'{name} Locking',
                                                     vehicle=vehicle)
                locking_accessory.set_info_service(firmware_revision=vehicle_software_version, manufacturer=manufacturer, model=model,
                                                   serial_number=f'{vin}-locking')
                self.set_config_item(locking_accessory.id_str, locking_accessory.vin, 'category', locking_accessory.category)
                self.set_config_item(locking_accessory.id_str, locking_accessory.vin, 'services',
                                     [service.display_name for service in locking_accessory.services])
                # Add the accessory to the bridge if not known
                if locking_accessory.aid not in self.accessories:
                    self.add_accessory(locking_accessory)
                # Replace the accessory if it is known but not of the correct type (was Dummy before)
                else:
                    self.accessories[locking_accessory.aid] = locking_accessory
                config_changed = True

        if config_changed:
            self.driver.config_changed()
            LOG.debug('Config changed, updating driver and persisting config')

    def get_existing_aid(self, id_str: str, vin: str) -> Optional[int]:
        """
        Retrieve the existing accessory ID (AID) for a given identifier string and vehicle identification number (VIN).

        Args:
            id_str (str): The identifier string associated with the accessory.
            vin (str): The vehicle identification number.

        Returns:
            Optional[int]: The accessory ID (AID) if it exists, otherwise None.
        """
        identifier = f'{vin}-{id_str}'
        aid: Optional[int] = None
        if identifier in self.__accessory_config and 'aid' in self.__accessory_config[identifier] \
                and self.__accessory_config[identifier]['aid'] is not None:
            aid = self.__accessory_config[identifier]['aid']
        return aid

    def select_aid(self, id_str: str, vin: str) -> int:
        """
        Selects or generates an accessory ID (aid) for a given accessory identifier.

        This method checks if an accessory ID (aid) already exists for the given
        combination of `id` and `vin` in the accessory configuration. If it exists,
        it returns the existing aid. If it does not exist, it generates a new aid,
        updates the accessory configuration, and returns the new aid.

        Args:
            id_str (str): The unique identifier for the accessory type.
            vin (str): The vehicle identification number.

        Returns:
            int: The accessory ID (aid) for the given accessory identifier.
        """
        aid = self.get_existing_aid(id_str=id_str, vin=vin)
        identifier = f'{vin}-{id_str}'
        if aid is None:
            new_aid: int = self.next_aid
            self.next_aid += 1
            if identifier in self.__accessory_config:
                self.__accessory_config[identifier]['aid'] = new_aid
            else:
                self.__accessory_config[identifier] = {'aid': new_aid}
            return new_aid
        return aid

    def set_config_item(self, id_str: str, vin: str, config_key: str, item: Any) -> None:
        """
        Set a configuration item for a specific accessory identified by a combination of VIN and ID string.

        Args:
            id_str (str): The identifier string for the accessory.
            vin (str): The vehicle identification number.
            config_key (str): The key for the configuration item.
            item (Any): The value to be set for the configuration item.

        Returns:
            None
        """
        identifier: str = f'{vin}-{id_str}'
        if identifier in self.__accessory_config:
            self.__accessory_config[identifier][config_key] = item
        else:
            self.__accessory_config[identifier] = {config_key: item}
        self.next_aid += 1

    def get_config_item(self, id_str: str, vin: str, config_key: str) -> Optional[Any]:
        """
        Retrieve a configuration item for a specific accessory.

        Args:
            id_str (str): The identifier string for the accessory.
            vin (str): The vehicle identification number.
            config_key (str): The key for the specific configuration item.

        Returns:
            Optional[Any]: The value of the configuration item if found, otherwise None.
        """
        identifier: str = f'{vin}-{id_str}'
        if identifier in self.__accessory_config and config_key in self.__accessory_config[identifier]:
            return self.__accessory_config[identifier][config_key]
        return None
