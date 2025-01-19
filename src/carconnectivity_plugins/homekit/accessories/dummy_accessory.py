""" DummyAccessory class module."""
from typing import Literal
from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_OTHER


class DummyAccessory(Accessory):
    """
    DummyAccessory class that inherits from Accessory.

    This is a placeholder when bringing up the plugin from stored values.
    If we don't offer these placeholders to HomeKit, it will remove the accessory from the Home app.

    Attributes:
        category (int): The category of the accessory, set to CATEGORY_OTHER.

    Methods:
        __init__(driver, aid, display_name):
            Initializes the DummyAccessory instance with the given driver, aid, and display_name.

        available:
            Property that always returns False, indicating the accessory is not available.
    """

    category: int = CATEGORY_OTHER

    def __init__(self, driver, aid, display_name) -> None:
        super().__init__(driver=driver, display_name=display_name, aid=aid)

    @Accessory.available.getter
    def available(self) -> Literal[False]:
        return False
