"""PetSafe selects: a litter box's rake timer."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PetSafeConfigEntry
from .entity import PetSafeLitterboxEntity

# Minutes after a cat leaves before the rake runs, as the ScoopFree app offers them
RAKE_TIMER = SelectEntityDescription(
    key="rake_timer",
    name="Rake Timer",
    entity_category=EntityCategory.CONFIG,
    options=["5", "10", "15", "20", "25", "30"],
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PetSafeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add every litter box's rake timer."""
    coordinator = entry.runtime_data
    async_add_entities(PetSafeRakeTimer(coordinator, api_name, RAKE_TIMER) for api_name in coordinator.data.litterboxes)


class PetSafeRakeTimer(PetSafeLitterboxEntity, SelectEntity):
    """A litter box's rake timer (minutes)."""

    @property
    def current_option(self) -> str:
        """The timer's minutes."""
        return str(self.litterbox.device.data["shadow"]["state"]["reported"]["rakeDelayTime"])

    async def async_select_option(self, option: str) -> None:
        """Change the timer, then read the litter box again."""
        await self.litterbox.device.modify_timer(int(option), False)
        await self.coordinator.async_request_refresh()
