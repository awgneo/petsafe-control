"""PetSafe buttons: feed a feeder's portion; rake or reset a litter box."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PetSafeConfigEntry
from .entity import PetSafeFeederEntity, PetSafeLitterboxEntity
from .petsafe_api.devices import DeviceScoopfree


@dataclass(frozen=True, kw_only=True)
class LitterboxButtonDescription(ButtonEntityDescription):
    """A litter box action."""

    press_fn: Callable[[DeviceScoopfree], Awaitable[object]]


FEED = ButtonEntityDescription(key="feed", name="Feed")

LITTERBOX_BUTTONS: tuple[LitterboxButtonDescription, ...] = (
    LitterboxButtonDescription(key="clean", name="Clean", press_fn=lambda device: device.rake(False)),
    LitterboxButtonDescription(key="reset", name="Reset", press_fn=lambda device: device.reset(0, False)),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PetSafeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add every feeder's Feed button and every litter box's buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(PetSafeFeedButton(coordinator, api_name, FEED) for api_name in coordinator.data.feeders),
            *(
                PetSafeLitterboxButton(coordinator, api_name, description)
                for api_name in coordinator.data.litterboxes
                for description in LITTERBOX_BUTTONS
            ),
        ]
    )


class PetSafeFeedButton(PetSafeFeederEntity, ButtonEntity):
    """Feeds the feeder's portion."""

    async def async_press(self) -> None:
        """Feed the portion now."""
        await self.coordinator.async_feed(self.api_name)


class PetSafeLitterboxButton(PetSafeLitterboxEntity, ButtonEntity):
    """A litter box action."""

    entity_description: LitterboxButtonDescription

    async def async_press(self) -> None:
        """Do it, then read the litter box again."""
        await self.entity_description.press_fn(self.litterbox.device)
        await self.coordinator.async_request_refresh()
