"""Tests for the feeders' switches and schedules, and the litter box's controls."""

from fakes import EVA, LITTERBOX, SHILOH
from homeassistant.const import STATE_OFF, STATE_ON

from custom_components.petsafe.const import DOMAIN


async def test_switches(hass, cloud, setup) -> None:
    """A switch changes the feeder's setting and shows it."""
    assert hass.states.get("switch.shiloh_feeder_child_lock").state == STATE_OFF
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.shiloh_feeder_child_lock"}, blocking=True)
    assert ("PUT", f"smart-feed/feeders/{SHILOH}/settings/child_lock", {"value": True}) in cloud.sent
    assert hass.states.get("switch.shiloh_feeder_child_lock").state == STATE_ON
    assert hass.states.get("switch.eva_feeder_feeding_paused").state == STATE_ON


async def test_schedules(hass, cloud, setup) -> None:
    """Schedules are added, changed and removed at a time, as PetSafe writes it (HH:MM)."""
    target = {"entity_id": "button.shiloh_feeder_feed"}
    await hass.services.async_call(DOMAIN, "add_schedule", {**target, "time": "12:30:00", "amount": 2}, blocking=True)
    assert ("POST", f"smart-feed/feeders/{SHILOH}/schedules", {"time": "12:30", "amount": 2}) in cloud.sent
    await hass.services.async_call(DOMAIN, "modify_schedule", {**target, "time": "08:00", "amount": 6}, blocking=True)
    assert ("PUT", f"smart-feed/feeders/{SHILOH}/schedules/11", {"time": "08:00", "amount": 6}) in cloud.sent
    await hass.services.async_call(DOMAIN, "delete_schedule", {**target, "time": "18:00"}, blocking=True)
    assert [s["time"] for s in cloud.schedules[SHILOH]] == ["08:00", "12:30"]
    await hass.services.async_call(DOMAIN, "delete_all_schedules", target, blocking=True)
    assert cloud.schedules[SHILOH] == []
    assert cloud.schedules[EVA] == []


async def test_litterbox_controls(hass, cloud, setup) -> None:
    """Clean rakes now; the rake timer changes the litter box's delay."""
    await hass.services.async_call("button", "press", {"entity_id": "button.litter_box_clean"}, blocking=True)
    assert ("POST", f"scoopfree/product/product/{LITTERBOX}/rake-now", {}) in cloud.sent
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.litter_box_rake_timer", "option": "20"}, blocking=True
    )
    assert ("PATCH", f"scoopfree/product/product/{LITTERBOX}/shadow", {"rakeDelayTime": 20}) in cloud.sent


async def test_unload(hass, setup) -> None:
    """The account unloads."""
    assert await hass.config_entries.async_unload(setup.entry_id)
