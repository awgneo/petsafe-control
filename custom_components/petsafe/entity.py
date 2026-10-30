"""The base of every PetSafe entity: one device, found again in each update by its PetSafe name."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FEEDER_MODEL_GEN1, MANUFACTURER
from .coordinator import Feeder, Litterbox, PetSafeCoordinator


class PetSafeEntity(CoordinatorEntity[PetSafeCoordinator]):
    """An entity of one PetSafe device; its unique id is the device's PetSafe name and the description's key."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PetSafeCoordinator, api_name: str, description: EntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.api_name = api_name
        self.entity_description = description
        self._attr_unique_id = f"{api_name}_{description.key}"


class PetSafeFeederEntity(PetSafeEntity):
    """An entity of a Smart Feed feeder."""

    def __init__(self, coordinator: PetSafeCoordinator, api_name: str, description: EntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, api_name, description)
        device = coordinator.data.feeders[api_name].device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api_name)},
            manufacturer=MANUFACTURER,
            name=device.friendly_name,
            sw_version=device.firmware,
            # Gen 1 feeders report no product name
            model=device.product_name or FEEDER_MODEL_GEN1,
        )

    @property
    def feeder(self) -> Feeder:
        """The feeder as last read."""
        return self.coordinator.data.feeders[self.api_name]

    @property
    def available(self) -> bool:
        """Whether the last read found the feeder."""
        return super().available and self.api_name in self.coordinator.data.feeders


class PetSafeLitterboxEntity(PetSafeEntity):
    """An entity of a ScoopFree litter box."""

    def __init__(self, coordinator: PetSafeCoordinator, api_name: str, description: EntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, api_name, description)
        device = coordinator.data.litterboxes[api_name].device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api_name)},
            manufacturer=MANUFACTURER,
            name=device.friendly_name,
            model=device.product_name,
            sw_version=device.firmware,
        )

    @property
    def litterbox(self) -> Litterbox:
        """The litter box as last read."""
        return self.coordinator.data.litterboxes[self.api_name]

    @property
    def available(self) -> bool:
        """Whether the last read found the litter box."""
        return super().available and self.api_name in self.coordinator.data.litterboxes
