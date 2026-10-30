"""PetSafe's actions: feed, prime, and a feeder's schedules, for the feeders an action targets."""

from __future__ import annotations

import datetime

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)

from .const import (
    ATTR_AMOUNT,
    ATTR_CUPS,
    ATTR_SLOW_FEED,
    ATTR_TIME,
    DOMAIN,
    EIGHTHS_PER_CUP,
    MAX_EIGHTHS,
    MIN_EIGHTHS,
    PRIME_EIGHTHS,
    SERVICE_ADD_SCHEDULE,
    SERVICE_DELETE_ALL_SCHEDULES,
    SERVICE_DELETE_SCHEDULE,
    SERVICE_FEED,
    SERVICE_MODIFY_SCHEDULE,
    SERVICE_PRIME,
)
from .coordinator import PetSafeCoordinator

AMOUNT = vol.All(vol.Coerce(int), vol.Range(min=MIN_EIGHTHS, max=MAX_EIGHTHS))
CUPS = vol.All(vol.Coerce(float), vol.Range(min=MIN_EIGHTHS / EIGHTHS_PER_CUP, max=MAX_EIGHTHS / EIGHTHS_PER_CUP))

FEED_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Exclusive(ATTR_AMOUNT, "amount"): AMOUNT,
        vol.Exclusive(ATTR_CUPS, "amount"): CUPS,
        vol.Optional(ATTR_SLOW_FEED): cv.boolean,
    }
)
SCHEDULE_SCHEMA = cv.make_entity_service_schema({vol.Required(ATTR_TIME): cv.time, vol.Required(ATTR_AMOUNT): AMOUNT})
TIME_SCHEMA = cv.make_entity_service_schema({vol.Required(ATTR_TIME): cv.time})
TARGET_SCHEMA = cv.make_entity_service_schema({})


def schedule_time(time: datetime.time) -> str:
    """A schedule's time as PetSafe writes it (HH:MM)."""
    return time.strftime("%H:%M")


@callback
def targeted_feeders(hass: HomeAssistant, call: ServiceCall) -> list[tuple[PetSafeCoordinator, str]]:
    """The feeders an action targets (by entity, device, area, floor or label): their coordinator and PetSafe name."""
    selected = async_extract_referenced_entity_ids(hass, TargetSelection(call.data), primary_entities_only=False)
    entity_registry = er.async_get(hass)
    device_ids = set(selected.referenced_devices)
    for entity_id in selected.referenced | selected.indirectly_referenced:
        if (entity := entity_registry.async_get(entity_id)) and entity.device_id:
            device_ids.add(entity.device_id)

    device_registry = dr.async_get(hass)
    feeders = []
    for device_id in sorted(device_ids):
        if not (device := device_registry.async_get(device_id)):
            continue
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if not entry or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
                continue
            coordinator: PetSafeCoordinator = entry.runtime_data
            feeders.extend(
                (coordinator, api_name)
                for domain, api_name in device.identifiers
                if domain == DOMAIN and api_name in coordinator.data.feeders
            )
    if not feeders:
        raise ServiceValidationError("The action targets no PetSafe feeder")
    return feeders


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register PetSafe's actions."""

    async def feed(call: ServiceCall) -> None:
        """Feed now: the amount given (eighths or cups), else each feeder's portion."""
        eighths = call.data.get(ATTR_AMOUNT)
        if ATTR_CUPS in call.data:
            eighths = round(call.data[ATTR_CUPS] * EIGHTHS_PER_CUP)
        for coordinator, api_name in targeted_feeders(hass, call):
            await coordinator.async_feed(api_name, eighths, call.data.get(ATTR_SLOW_FEED))

    async def prime(call: ServiceCall) -> None:
        """Feed 5/8 cup to fill the chute, never slowly."""
        for coordinator, api_name in targeted_feeders(hass, call):
            await coordinator.async_feed(api_name, PRIME_EIGHTHS, False)

    async def add_schedule(call: ServiceCall) -> None:
        """Add a daily feeding."""
        for coordinator, api_name in targeted_feeders(hass, call):
            device = coordinator.data.feeders[api_name].device
            await device.schedule_feed(schedule_time(call.data[ATTR_TIME]), call.data[ATTR_AMOUNT], False)
            await coordinator.async_request_refresh()

    async def modify_schedule(call: ServiceCall) -> None:
        """Change the amount of the daily feeding at a time."""
        for coordinator, api_name in targeted_feeders(hass, call):
            device = coordinator.data.feeders[api_name].device
            for schedule in await device.get_schedules():
                if schedule["time"] == schedule_time(call.data[ATTR_TIME]):
                    await device.modify_schedule(schedule["time"], call.data[ATTR_AMOUNT], str(schedule["id"]), False)
            await coordinator.async_request_refresh()

    async def delete_schedule(call: ServiceCall) -> None:
        """Remove the daily feeding at a time."""
        for coordinator, api_name in targeted_feeders(hass, call):
            device = coordinator.data.feeders[api_name].device
            for schedule in await device.get_schedules():
                if schedule["time"] == schedule_time(call.data[ATTR_TIME]):
                    await device.delete_schedule(str(schedule["id"]), False)
            await coordinator.async_request_refresh()

    async def delete_all_schedules(call: ServiceCall) -> None:
        """Remove every daily feeding."""
        for coordinator, api_name in targeted_feeders(hass, call):
            await coordinator.data.feeders[api_name].device.delete_all_schedules(False)
            await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_FEED, feed, schema=FEED_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_PRIME, prime, schema=TARGET_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_SCHEDULE, add_schedule, schema=SCHEDULE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_MODIFY_SCHEDULE, modify_schedule, schema=SCHEDULE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_SCHEDULE, delete_schedule, schema=TIME_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_ALL_SCHEDULES, delete_all_schedules, schema=TARGET_SCHEMA)
