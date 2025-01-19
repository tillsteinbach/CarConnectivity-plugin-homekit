""" HomeKit Bridge for CarConnectivity """
from __future__ import annotations
from typing import TYPE_CHECKING

import logging
import json

from carconnectivity.drive import GenericDrive
from pyhap.accessory import Bridge
from pyhap.accessory_driver import AccessoryDriver

from carconnectivity.observable import Observable
from carconnectivity.vehicle import GenericVehicle, ElectricVehicle
from carconnectivity._version import __version__ as __carconnectivity_version__

from carconnectivity_plugins.homekit.accessories.dummy_accessory import DummyAccessory
from carconnectivity_plugins.homekit.accessories.climatization import ClimatizationAccessory
from carconnectivity_plugins.homekit._version import __version__


if TYPE_CHECKING:
    from typing import Optional, Any, Dict

    from carconnectivity.carconnectivity import CarConnectivity

LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.homekit.bridge")


class CarConnectivityBridge(Bridge):
    """VWsfriend Bridge"""

    def __init__(self, car_connectivity: CarConnectivity, driver: AccessoryDriver, display_name: str = 'CarConnectivity',
                 accessory_config_file: str = '~/.carconnectivity/homekit-accessory.config'):
        super().__init__(driver=driver, display_name=display_name, )

        self.set_info_service(f'{__carconnectivity_version__} (HomeKit Plugin {__version__})', 'Till Steinbach', 'CarConnectivity', None)

        self.car_connectivity: CarConnectivity = car_connectivity
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

        if self.car_connectivity.garage is not None:
            for vehicle in self.car_connectivity.garage.list_vehicles():
                self.update(vehicle=vehicle)
        car_connectivity.garage.add_observer(observer=self.__on_garage_update, flag=Observable.ObserverEvent.ENABLED, on_transaction_end=True)

    def __on_garage_update(self, element: Any, flags: Observable.ObserverEvent) -> None:
        """Update the accessories when the garage is updated."""
        if (flags & Observable.ObserverEvent.ENABLED) and isinstance(element, GenericVehicle):
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

    def update(self, vehicle: GenericVehicle):  # noqa: C901
        config_changed = False
        if vehicle.enabled and vehicle.vin.enabled and vehicle.vin.value is not None:
            vin: str = vehicle.vin.value
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
            if vehicle.climatization is not None and vehicle.climatization.enabled:
                climatization_accessory = ClimatizationAccessory(driver=self.driver, bridge=self, aid=self.select_aid('Climatization', vin),
                                                                    id_str='Climatization', vin=vin, display_name=f'{name} Climatization',
                                                                    vehicle=vehicle)
                climatization_accessory.set_info_service(firmware_revision=vehicle_software_version, manufacturer=manufacturer, model=model,
                                                         serial_number=f'{vin}-climatization')
                self.set_config_item(climatization_accessory.id_str, climatization_accessory.vin, 'category', climatization_accessory.category)
                self.set_config_item(climatization_accessory.id_str, climatization_accessory.vin, 'services',
                                        [service.display_name for service in climatization_accessory.services])
                if climatization_accessory.aid not in self.accessories:
                    self.add_accessory(climatization_accessory)
                else:
                    self.accessories[climatization_accessory.aid] = climatization_accessory
                config_changed = True
        if config_changed:
            self.driver.config_changed()
            LOG.debug('Config changed, updating driver and persisting config')
            self.persist_config()

                        


        #         if vehicle.statusExists('charging', 'batteryStatus'):
        #             batteryStatus = vehicle.domains['charging']['batteryStatus']
        #         else:
        #             batteryStatus = None

        #         if vehicle.statusExists('charging', 'chargingStatus'):
        #             chargingStatus = vehicle.domains['charging']['chargingStatus']
        #         else:
        #             chargingStatus = None

        #         climatizationAccessory = Climatization(driver=self.driver, bridge=self, aid=self.select_aid('Climatization', vin), id='Climatization', vin=vin,
        #                                                displayName=f'{nickname} Climatization', climatizationStatus=climatizationStatus,
        #                                                climatizationSettings=climatizationSettings, batteryStatus=batteryStatus, chargingStatus=chargingStatus,
        #                                                climatizationControl=vehicle.controls.climatizationControl)
        #         climatizationAccessory.set_info_service(manufacturer=manufacturer, model=model, serial_number=f'{vin}-climatization')
        #         self.set_config_item(climatizationAccessory.id, climatizationAccessory.vin, 'category', climatizationAccessory.category)
        #         self.set_config_item(climatizationAccessory.id, climatizationAccessory.vin, 'services',
        #                            [service.display_name for service in climatizationAccessory.services])
        #         if climatizationAccessory.aid not in self.accessories:
        #             self.add_accessory(climatizationAccessory)
        #         else:
        #             self.accessories[climatizationAccessory.aid] = climatizationAccessory
        #         configChanged = True

        #     if vehicle.statusExists('charging', 'chargingStatus'):
        #         chargingStatus = vehicle.domains['charging']['chargingStatus']

        #         if vehicle.statusExists('charging', 'plugStatus'):
        #             plugStatus = vehicle.domains['charging']['plugStatus']
        #         else:
        #             plugStatus = None

        #         if vehicle.statusExists('charging', 'batteryStatus'):
        #             batteryStatus = vehicle.domains['charging']['batteryStatus']
        #         else:
        #             batteryStatus = None

        #         chargingAccessory = Charging(driver=self.driver, bridge=self, aid=self.select_aid('Charging', vin), id='Charging', vin=vin,
        #                                      displayName=f'{nickname} Charging', chargingStatus=chargingStatus, plugStatus=plugStatus,
        #                                      batteryStatus=batteryStatus, chargingControl=vehicle.controls.chargingControl)
        #         chargingAccessory.set_info_service(manufacturer=manufacturer, model=model, serial_number=f'{vin}-charging')
        #         self.set_config_item(chargingAccessory.id, chargingAccessory.vin, 'category', chargingAccessory.category)
        #         self.set_config_item(chargingAccessory.id, chargingAccessory.vin, 'services', [service.display_name for service in chargingAccessory.services])
        #         if chargingAccessory.aid not in self.accessories:
        #             self.add_accessory(chargingAccessory)
        #         else:
        #             self.accessories[chargingAccessory.aid] = chargingAccessory
        #         configChanged = True

        #     if vehicle.statusExists('charging', 'plugStatus'):
        #         plugStatus = vehicle.domains['charging']['plugStatus']

        #         plugAccessory = Plug(driver=self.driver, bridge=self, aid=self.select_aid('ChargingPlug', vin), id='ChargingPlug', vin=vin,
        #                              displayName=f'{nickname} Charging Plug', plugStatus=plugStatus)
        #         plugAccessory.set_info_service(manufacturer=manufacturer, model=model, serial_number=f'{vin}-charging_plug')
        #         self.set_config_item(plugAccessory.id, plugAccessory.vin, 'category', plugAccessory.category)
        #         self.set_config_item(plugAccessory.id, plugAccessory.vin, 'services', [service.display_name for service in plugAccessory.services])
        #         if plugAccessory.aid not in self.accessories:
        #             self.add_accessory(plugAccessory)
        #         else:
        #             self.accessories[plugAccessory.aid] = plugAccessory
        #         configChanged = True

        #     if vehicle.statusExists('access', 'accessStatus') and vehicle.domains['access']['accessStatus'].carCapturedTimestamp.enabled:
        #         accessStatus = vehicle.domains['access']['accessStatus']

        #         if vehicle.controls.accessControl is not None and vehicle.controls.accessControl.enabled:
        #             accessControl = vehicle.controls.accessControl
        #         else:
        #             accessControl = None

        #         lockingSystemAccessory = LockingSystem(driver=self.driver, bridge=self, aid=self.select_aid('LockingSystem', vin), id='LockingSystem', vin=vin,
        #                                                displayName=f'{nickname} Locking System', accessStatus=accessStatus, accessControl=accessControl)
        #         lockingSystemAccessory.set_info_service(manufacturer=manufacturer, model=model, serial_number=f'{vin}-locking_system')
        #         self.set_config_item(lockingSystemAccessory.id, lockingSystemAccessory.vin, 'category', lockingSystemAccessory.category)
        #         self.set_config_item(lockingSystemAccessory.id, lockingSystemAccessory.vin, 'services',
        #                            [service.display_name for service in lockingSystemAccessory.services])
        #         if lockingSystemAccessory.aid not in self.accessories:
        #             self.add_accessory(lockingSystemAccessory)
        #         else:
        #             self.accessories[lockingSystemAccessory.aid] = lockingSystemAccessory
        #         configChanged = True

        #     if vehicle.controls.honkAndFlashControl is not None and vehicle.controls.honkAndFlashControl.enabled:
        #         honkAndFlashControl = vehicle.controls.honkAndFlashControl

        #         flashingAccessory = Flashing(driver=self.driver, bridge=self, aid=self.select_aid('Flashing', vin), id='Flashing', vin=vin,
        #                                      displayName=f'{nickname} Flashing', flashControl=honkAndFlashControl)
        #         flashingAccessory.set_info_service(manufacturer=manufacturer, model=model, serial_number=f'{vin}-flashing')
        #         self.set_config_item(flashingAccessory.id, flashingAccessory.vin, 'category', flashingAccessory.category)
        #         self.set_config_item(flashingAccessory.id, flashingAccessory.vin, 'services',
        #                            [service.display_name for service in flashingAccessory.services])
        #         if flashingAccessory.aid not in self.accessories:
        #             self.add_accessory(flashingAccessory)
        #         else:
        #             self.accessories[flashingAccessory.aid] = flashingAccessory
        #         configChanged = True

        #     if vehicle.statusExists('measurements', 'temperatureBatteryStatus') \
        #             and vehicle.domains['measurements']['temperatureBatteryStatus'].carCapturedTimestamp.enabled:
        #         temperatureBatteryStatus = vehicle.domains['measurements']['temperatureBatteryStatus']

        #         if vehicle.statusExists('charging', 'batteryStatus'):
        #             batteryStatus = vehicle.domains['charging']['batteryStatus']

        #             if vehicle.statusExists('charging', 'chargingStatus'):
        #                 chargingStatus = vehicle.domains['charging']['chargingStatus']
        #             else:
        #                 chargingStatus = None

        #             batteryTemperatureAccessory = BatteryTemperature(driver=self.driver, bridge=self, aid=self.select_aid('BatteryTemperature', vin),
        #                                                              id='BatteryTemperature', vin=vin, displayName=f'{nickname} Battery Temperature',
        #                                                              batteryStatus=batteryStatus, batteryTemperatureStatus=temperatureBatteryStatus,
        #                                                              chargingStatus=chargingStatus)

        #             batteryTemperatureAccessory.set_info_service(manufacturer=manufacturer, model=model, serial_number=f'{vin}-battery_termperature')
        #             self.set_config_item(batteryTemperatureAccessory.id, batteryTemperatureAccessory.vin, 'category', batteryTemperatureAccessory.category)
        #             self.set_config_item(batteryTemperatureAccessory.id, batteryTemperatureAccessory.vin, 'services',
        #                                [service.display_name for service in batteryTemperatureAccessory.services])
        #             if batteryTemperatureAccessory.aid not in self.accessories:
        #                 self.add_accessory(batteryTemperatureAccessory)
        #             else:
        #                 self.accessories[batteryTemperatureAccessory.aid] = batteryTemperatureAccessory
        #             configChanged = True

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
        identifier = f'{vin}-{id_str}'
        if identifier in self.__accessory_config and 'aid' in self.__accessory_config[identifier] \
                and self.__accessory_config[identifier]['aid'] is not None:
            aid: int = self.__accessory_config[identifier]['aid']
        else:
            aid: int = self.next_aid
            self.next_aid += 1
            if identifier in self.__accessory_config:
                self.__accessory_config[identifier]['aid'] = aid
            else:
                self.__accessory_config[identifier] = {'aid': aid}
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
