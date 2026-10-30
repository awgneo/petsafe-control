"""PetSafe switches: a feeder's paused schedules, child lock and slow feed."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PetSafeConfigEntry
from .entity import PetSafeFeederEntity
from .petsafe_api.devices import DeviceSmartFeed


@dataclass(frozen=True, kw_only=True)
class FeederSwitchDescription(SwitchEntityDescription):
    """A feeder setting: how it's read, and how it's changed."""

    is_on_fn: Callable[[DeviceSmartFeed], bool]
    set_fn: Callable[[DeviceSmartFeed, bool], Awaitable[None]]


FEEDER_SWITCHES: tuple[FeederSwitchDescription, ...] = (
    FeederSwitchDescription(
        key="feeding_paused",
        name="Feeding Paused",
        icon="mdi:pause",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.is_paused,
        set_fn=lambda device, value: device.pause(value),
    ),
    FeederSwitchDescription(
        key="child_lock",
        name="Child Lock",
        icon="mdi:lock-open",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.is_locked,
        set_fn=lambda device, value: device.lock(value),
    ),
    FeederSwitchDescription(
        key="slow_feed",
        name="Slow Feed",
        icon="mdi:tortoise",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.is_slow_feed,
        set_fn=lambda device, value: device.slow_feed(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PetSafeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add every feeder's switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        PetSafeFeederSwitch(coordinator, api_name, description)
        for api_name in coordinator.data.feeders
        for description in FEEDER_SWITCHES
    )


class PetSafeFeederSwitch(PetSafeFeederEntity, SwitchEntity):
    """A feeder setting."""

    entity_description: FeederSwitchDescription

    @property
    def is_on(self) -> bool:
        """Whether the setting is on."""
        return self.entity_description.is_on_fn(self.feeder.device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._set(False)

    async def _set(self, value: bool) -> None:
        """Change the setting, then read the feeder again (pausing changes its next feeding)."""
        await self.entity_description.set_fn(self.feeder.device, value)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
