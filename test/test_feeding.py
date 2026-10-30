"""Tests for feeding: the portion, the Feed button and the feed action."""

from unittest.mock import patch

import httpx
import pytest
from fakes import EVA, SHILOH
from homeassistant.core import State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import (
    mock_restore_cache_with_extra_data,
)

from custom_components.petsafe.const import DOMAIN


async def press(hass, entity_id: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)


async def test_portion_starts_from_the_last_feeding(hass, setup) -> None:
    """Without a portion kept from before, each feeder's is what it last gave."""
    assert hass.states.get("number.eva_feeder_portion").state == "3.0"
    assert hass.states.get("number.shiloh_feeder_portion").state == "1.0"


async def test_feed_button_feeds_the_portion(hass, cloud, setup) -> None:
    """The Feed button gives the portion, not 1/8 cup; a changed portion is what's fed next."""
    await press(hass, "button.eva_feeder_feed")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.eva_feeder_portion", "value": 2.5}, blocking=True
    )
    await press(hass, "button.eva_feeder_feed")
    assert cloud.meals() == [(EVA, 24), (EVA, 20)]


async def test_portion_is_kept_across_restarts(hass, freezer, cloud, cognito, mock_config_entry) -> None:
    """A portion set before a restart comes back after it."""
    number = {
        "native_value": 1.5,
        "native_min_value": 0.125,
        "native_max_value": 4.0,
        "native_step": 0.125,
        "native_unit_of_measurement": "cups",
    }
    mock_restore_cache_with_extra_data(hass, [(State("number.shiloh_feeder_portion", "1.5"), number)])
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.petsafe.get_async_client", return_value=httpx.AsyncClient(transport=cloud.transport)):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("number.shiloh_feeder_portion").state == "1.5"
        await press(hass, "button.shiloh_feeder_feed")
    assert cloud.meals() == [(SHILOH, 12)]


async def test_feed_action_amounts(hass, cloud, setup) -> None:
    """The feed action gives eighths, cups, or without either the feeder's portion."""
    target = {"entity_id": "button.shiloh_feeder_feed"}
    await hass.services.async_call(DOMAIN, "feed", {**target, "amount": 2}, blocking=True)
    await hass.services.async_call(DOMAIN, "feed", {**target, "cups": 0.5}, blocking=True)
    await hass.services.async_call(DOMAIN, "feed", target, blocking=True)
    assert cloud.meals() == [(SHILOH, 2), (SHILOH, 4), (SHILOH, 8)]
    # A snack leaves the portion as it was
    assert hass.states.get("number.shiloh_feeder_portion").state == "1.0"


async def test_feed_action_slow_feed(hass, cloud, setup) -> None:
    """Slow feed follows the feeder's setting unless the action says."""
    await hass.services.async_call(
        DOMAIN, "feed", {"entity_id": "button.eva_feeder_feed", "slow_feed": True}, blocking=True
    )
    assert cloud.sent[-1][2] == {"amount": 24, "slow_feed": True}


async def test_feed_action_targets_only_its_feeders(hass, cloud, setup) -> None:
    """Feeding by area feeds that area's feeders only, however many actions came before."""
    areas = ar.async_get(hass)
    devices = dr.async_get(hass)
    for thing, room in ((EVA, "Den"), (SHILOH, "Kitchen")):
        area = areas.async_create(room)
        device = devices.async_get_device_by_identifier((DOMAIN, thing), setup.entry_id)
        devices.async_update_device(device.id, area_id=area.id)

    await hass.services.async_call(DOMAIN, "feed", {"area_id": "den", "amount": 1}, blocking=True)
    await hass.services.async_call(DOMAIN, "feed", {"area_id": "kitchen", "amount": 1}, blocking=True)
    assert cloud.meals() == [(EVA, 1), (SHILOH, 1)]


async def test_feed_action_without_a_feeder(hass, setup) -> None:
    """An action that targets no feeder says so."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "feed", {"entity_id": "sensor.litter_box_rake_counter", "amount": 1}, blocking=True
        )


async def test_prime(hass, cloud, setup) -> None:
    """Priming gives 5/8 cup, never slowly."""
    await hass.services.async_call(DOMAIN, "prime", {"entity_id": "button.eva_feeder_feed"}, blocking=True)
    assert cloud.sent[-1][2] == {"amount": 5, "slow_feed": False}
