"""PetSafe numbers: a feeder's portion, what its Feed button, the feed action and Claude give by default."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EIGHTHS_PER_CUP, MAX_EIGHTHS, MIN_EIGHTHS
from .coordinator import PetSafeConfigEntry
from .entity import PetSafeFeederEntity

PORTION = NumberEntityDescription(
    key="portion",
    name="Portion",
    icon="mdi:cup",
    entity_category=EntityCategory.CONFIG,
    native_unit_of_measurement="cups",
    native_min_value=MIN_EIGHTHS / EIGHTHS_PER_CUP,
    native_max_value=MAX_EIGHTHS / EIGHTHS_PER_CUP,
    native_step=1 / EIGHTHS_PER_CUP,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PetSafeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add every feeder's portion."""
    coordinator = entry.runtime_data
    async_add_entities(PetSafePortion(coordinator, api_name, PORTION) for api_name in coordinator.data.feeders)


class PetSafePortion(PetSafeFeederEntity, RestoreNumber):
    """A feeder's usual feeding, in cups: kept by Home Assistant (PetSafe keeps none), starting from its last feeding."""

    async def async_added_to_hass(self) -> None:
        """Take the portion back from before a restart; a new one starts from what the feeder last gave."""
        await super().async_added_to_hass()
        if (restored := await self.async_get_last_number_data()) and restored.native_value is not None:
            self.coordinator.portions[self.api_name] = round(restored.native_value * EIGHTHS_PER_CUP)
        else:
            self.coordinator.portions[self.api_name] = self.coordinator.portion(self.api_name)

    @property
    def native_value(self) -> float:
        """The portion, in cups."""
        return self.coordinator.portion(self.api_name) / EIGHTHS_PER_CUP

    async def async_set_native_value(self, value: float) -> None:
        """Change the portion."""
        self.coordinator.portions[self.api_name] = round(value * EIGHTHS_PER_CUP)
        self.async_write_ha_state()
