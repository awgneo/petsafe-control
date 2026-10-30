"""PetSafe sensors: a feeder's battery, food, feedings and signal; a litter box's raking and signal."""

from __future__ import annotations

import datetime
import time
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    CAT_IN_BOX,
    ERROR_SENSOR_BLOCKED,
    RAKE_BUTTON_DETECTED,
    RAKE_FINISHED,
    RAKE_NOW,
)
from .coordinator import Feeder, Litterbox, PetSafeConfigEntry
from .entity import PetSafeFeederEntity, PetSafeLitterboxEntity
from .petsafe_api.const import FOOD_LEVEL_FULL, FOOD_LEVEL_LOW

FOOD_LEVELS = {FOOD_LEVEL_FULL: "full", FOOD_LEVEL_LOW: "low"}


@dataclass(frozen=True, kw_only=True)
class FeederSensorDescription(SensorEntityDescription):
    """A feeder sensor, read from the feeder."""

    value_fn: Callable[[Feeder], StateType | datetime.datetime]


@dataclass(frozen=True, kw_only=True)
class LitterboxSensorDescription(SensorEntityDescription):
    """A litter box sensor, read from the litter box."""

    value_fn: Callable[[Litterbox], StateType | datetime.datetime]


def battery_level(feeder: Feeder) -> int | None:
    """The battery's charge, or None when the feeder runs on its adapter without batteries."""
    return feeder.device.battery_level if feeder.device.data["is_batteries_installed"] else None


def reported(litterbox: Litterbox) -> dict:
    """What the litter box last reported about itself."""
    return litterbox.device.data["shadow"]["state"]["reported"]


def last_cleaning(litterbox: Litterbox) -> datetime.datetime | None:
    """When the rake last finished."""
    for item in reversed(litterbox.activity):
        if item["payload"]["code"] == RAKE_FINISHED:
            return dt_util.utc_from_timestamp(int(item["payload"]["timestamp"]) / 1000)
    return None


def rake_status(litterbox: Litterbox) -> str | None:
    """What the rake is doing, from the newest activity that says: idle, timing (a cat was in), raking or jammed."""
    for item in reversed(litterbox.activity):
        code = item["payload"]["code"]
        if code == RAKE_FINISHED:
            return "idle"
        if code == CAT_IN_BOX:
            raking_at = int(item["payload"]["timestamp"]) / 1000 + reported(litterbox)["rakeDelayTime"] * 60
            return "raking" if raking_at <= time.time() else "timing"
        if code in (RAKE_BUTTON_DETECTED, RAKE_NOW):
            return "raking"
        if code == ERROR_SENSOR_BLOCKED:
            return "jammed"
    return None


FEEDER_SENSORS: tuple[FeederSensorDescription, ...] = (
    FeederSensorDescription(
        key="battery",
        name="Battery Level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=battery_level,
    ),
    FeederSensorDescription(
        key="last_feeding",
        name="Last Feeding",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda feeder: feeder.last_feeding,
    ),
    FeederSensorDescription(
        key="next_feeding",
        name="Next Feeding",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda feeder: feeder.next_feeding,
    ),
    FeederSensorDescription(
        key="food_level",
        name="Food Level",
        icon="mdi:bowl",
        value_fn=lambda feeder: FOOD_LEVELS.get(feeder.device.food_low_status, "empty"),
    ),
    FeederSensorDescription(
        key="signal_strength",
        name="Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda feeder: feeder.device.data["network_rssi"],
    ),
)

LITTERBOX_SENSORS: tuple[LitterboxSensorDescription, ...] = (
    LitterboxSensorDescription(
        key="rake_counter",
        name="Rake Counter",
        icon="mdi:rake",
        value_fn=lambda litterbox: reported(litterbox)["rakeCount"],
    ),
    LitterboxSensorDescription(key="rake_status", name="Rake Status", icon="mdi:rake", value_fn=rake_status),
    LitterboxSensorDescription(
        key="signal_strength",
        name="Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda litterbox: reported(litterbox)["rssi"],
    ),
    LitterboxSensorDescription(
        key="last_cleaning",
        name="Last Cleaning",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=last_cleaning,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PetSafeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add every feeder's and litter box's sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(
                PetSafeFeederSensor(coordinator, api_name, description)
                for api_name in coordinator.data.feeders
                for description in FEEDER_SENSORS
            ),
            *(
                PetSafeLitterboxSensor(coordinator, api_name, description)
                for api_name in coordinator.data.litterboxes
                for description in LITTERBOX_SENSORS
            ),
        ]
    )


class PetSafeFeederSensor(PetSafeFeederEntity, SensorEntity):
    """A feeder sensor."""

    entity_description: FeederSensorDescription

    @property
    def native_value(self) -> StateType | datetime.datetime:
        """The sensor's value."""
        return self.entity_description.value_fn(self.feeder)


class PetSafeLitterboxSensor(PetSafeLitterboxEntity, SensorEntity):
    """A litter box sensor."""

    entity_description: LitterboxSensorDescription

    @property
    def native_value(self) -> StateType | datetime.datetime:
        """The sensor's value."""
        return self.entity_description.value_fn(self.litterbox)
