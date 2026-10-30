"""The PetSafe integration: Smart Feed feeders and ScoopFree litter boxes, through PetSafe's cloud."""

from __future__ import annotations

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import PetSafeConfigEntry, PetSafeCoordinator
from .llm import async_setup_llm
from .petsafe_api import PetSafeClient
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register PetSafe's actions and its tools for assistants, once."""
    async_setup_services(hass)
    async_setup_llm(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PetSafeConfigEntry) -> bool:
    """Set up a PetSafe account: read its devices, then add their entities."""
    client = PetSafeClient(
        entry.data.get(CONF_EMAIL),
        entry.data.get(CONF_TOKEN),
        entry.data.get(CONF_REFRESH_TOKEN),
        entry.data.get(CONF_ACCESS_TOKEN),
        client=get_async_client(hass),
    )
    coordinator = PetSafeCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PetSafeConfigEntry) -> bool:
    """Unload a PetSafe account."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
