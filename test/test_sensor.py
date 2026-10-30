"""Tests for the feeders' and the litter box's sensors."""

import datetime

from fakes import EVA, NOON
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util


async def test_entities_keep_their_unique_ids(hass, setup) -> None:
    """Each entity's unique id is the device's PetSafe name and its key, as the original integration made them."""
    registry = er.async_get(hass)
    assert registry.async_get("sensor.eva_feeder_battery_level").unique_id == f"{EVA}_battery"
    assert registry.async_get("button.eva_feeder_feed").unique_id == f"{EVA}_feed"
    assert registry.async_get("switch.eva_feeder_child_lock").unique_id == f"{EVA}_child_lock"


async def test_last_feeding_is_the_newest(hass, setup) -> None:
    """PetSafe lists messages oldest first: the last feeding is the newest of them."""
    expected = dt_util.utc_from_timestamp(NOON).isoformat()
    assert hass.states.get("sensor.eva_feeder_last_feeding").state == expected
    assert hass.states.get("sensor.shiloh_feeder_last_feeding").state == expected


async def test_next_feeding(hass, setup) -> None:
    """The next scheduled time, in the feeder's timezone; none while its schedules are paused."""
    evening = datetime.datetime(2026, 10, 26, 18, 0, tzinfo=dt_util.get_time_zone("America/New_York"))
    assert hass.states.get("sensor.shiloh_feeder_next_feeding").state == evening.astimezone(datetime.UTC).isoformat()
    assert hass.states.get("sensor.eva_feeder_next_feeding").state == STATE_UNKNOWN


async def test_next_feeding_without_schedules(hass, cloud, setup) -> None:
    """A feeder without schedules has no next feeding (not an error every update)."""
    cloud.feeders[EVA]["settings"]["paused"] = False
    await setup.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.eva_feeder_next_feeding").state == STATE_UNKNOWN
    assert setup.runtime_data.last_update_success


async def test_next_feeding_tomorrow(hass, freezer, setup) -> None:
    """After the day's last scheduled feeding, the next is tomorrow's first."""
    freezer.move_to("2026-10-27 01:00:00+00:00")
    await setup.runtime_data.async_refresh()
    await hass.async_block_till_done()
    morning = datetime.datetime(2026, 10, 27, 8, 0, tzinfo=dt_util.get_time_zone("America/New_York"))
    assert hass.states.get("sensor.shiloh_feeder_next_feeding").state == morning.astimezone(datetime.UTC).isoformat()


async def test_battery_without_batteries(hass, setup) -> None:
    """A feeder on its adapter without batteries has no battery level, not 0%."""
    assert hass.states.get("sensor.eva_feeder_battery_level").state == STATE_UNKNOWN


async def test_feeder_readings(hass, setup) -> None:
    """Food level and signal strength."""
    assert hass.states.get("sensor.eva_feeder_food_level").state == "full"
    assert hass.states.get("sensor.eva_feeder_signal_strength").state == "-62"


async def test_litterbox(hass, setup) -> None:
    """A litter box's rake count, signal, last cleaning, and a cat in it past its timer."""
    assert hass.states.get("sensor.litter_box_rake_counter").state == "7"
    assert hass.states.get("sensor.litter_box_signal_strength").state == "-55"
    last = dt_util.utc_from_timestamp(NOON - 3600).isoformat()
    assert hass.states.get("sensor.litter_box_last_cleaning").state == last
    # The cat came in at 14:21:10 and the rake waits 15 minutes: at 15:00 it's raking
    assert hass.states.get("sensor.litter_box_rake_status").state == "raking"
    assert hass.states.get("select.litter_box_rake_timer").state == "15"
