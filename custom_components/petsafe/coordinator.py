"""PetSafe's devices, read from its cloud on one schedule, and the feeding every part of the integration shares."""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from datetime import timedelta

import httpx
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import MIN_EIGHTHS
from .petsafe_api import PetSafeClient
from .petsafe_api.devices import DeviceScoopfree, DeviceSmartFeed

_LOGGER = logging.getLogger(__name__)

# How often PetSafe's cloud is read: each feeder, its last feeding and schedules, and each litter box's activity
UPDATE_INTERVAL = timedelta(seconds=30)
# Unauthorized answers in a row before Home Assistant asks to sign in again (one alone is PetSafe's hiccup)
AUTH_FAILURES = 5

type PetSafeConfigEntry = ConfigEntry[PetSafeCoordinator]


@dataclass
class Feeder:
    """A Smart Feed feeder, with what its messages and schedules say."""

    device: DeviceSmartFeed
    # The newest feeding, and how much it gave (eighths of a cup)
    last_feeding: datetime.datetime | None
    last_amount: int | None
    # The next scheduled feeding; None with no schedule, or while schedules are paused
    next_feeding: datetime.datetime | None


@dataclass
class Litterbox:
    """A ScoopFree litter box, with its activity (oldest first, as PetSafe lists it)."""

    device: DeviceScoopfree
    activity: list[dict]


@dataclass
class PetSafeData:
    """Every device on the account, by its PetSafe name (api_name)."""

    feeders: dict[str, Feeder] = field(default_factory=dict)
    litterboxes: dict[str, Litterbox] = field(default_factory=dict)


def next_feeding(
    schedules: list[dict], timezone: datetime.tzinfo, now: datetime.datetime
) -> datetime.datetime | None:
    """The first scheduled time (HH:MM, in the feeder's timezone) after now, or None with no schedule."""
    times = sorted(datetime.time.fromisoformat(schedule["time"]) for schedule in schedules)
    today = now.astimezone(timezone).date()
    for day in (today, today + timedelta(days=1)):
        for time in times:
            at = datetime.datetime.combine(day, time, timezone)
            if at > now:
                return at
    return None


class PetSafeCoordinator(DataUpdateCoordinator[PetSafeData]):
    """Reads every PetSafe device; feeds; and keeps each feeder's portion."""

    config_entry: PetSafeConfigEntry

    def __init__(self, hass: HomeAssistant, api: PetSafeClient, entry: PetSafeConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, config_entry=entry, name="PetSafe", update_interval=UPDATE_INTERVAL)
        self.api = api
        # Each feeder's usual feeding (eighths of a cup), kept by its Portion number
        self.portions: dict[str, int] = {}
        self._auth_failures = 0

    async def _async_update_data(self) -> PetSafeData:
        """Read every device from PetSafe's cloud."""
        try:
            data = PetSafeData()
            for device in await self.api.get_feeders():
                data.feeders[device.api_name] = await self._read_feeder(device)
            for device in await self.api.get_litterboxes():
                data.litterboxes[device.api_name] = Litterbox(device, (await device.get_activity())["data"])
        except httpx.HTTPStatusError as ex:
            if ex.response.status_code in (401, 403):
                self._auth_failures += 1
                if self._auth_failures >= AUTH_FAILURES:
                    self._auth_failures = 0
                    raise ConfigEntryAuthFailed from ex
            raise UpdateFailed(f"PetSafe answered {ex.response.status_code}") from ex
        except httpx.HTTPError as ex:
            raise UpdateFailed(f"PetSafe can't be reached: {ex}") from ex
        self._auth_failures = 0
        return data

    async def _read_feeder(self, device: DeviceSmartFeed) -> Feeder:
        """A feeder with its newest feeding and next scheduled one."""
        feeding = await device.get_last_feeding()
        upcoming = None
        if not device.is_paused:
            timezone = dt_util.get_time_zone(device.data["settings"].get("timezone", "")) or dt_util.get_default_time_zone()
            upcoming = next_feeding(await device.get_schedules(), timezone, dt_util.utcnow())
        return Feeder(
            device=device,
            last_feeding=dt_util.utc_from_timestamp(feeding["payload"]["time"]) if feeding else None,
            last_amount=feeding["payload"]["amount"] if feeding else None,
            next_feeding=upcoming,
        )

    def portion(self, api_name: str) -> int:
        """A feeder's usual feeding (eighths): its Portion, else what it last gave, else one eighth."""
        if api_name in self.portions:
            return self.portions[api_name]
        feeder = self.data.feeders.get(api_name)
        return feeder.last_amount if feeder and feeder.last_amount else MIN_EIGHTHS

    async def async_feed(self, api_name: str, eighths: int | None = None, slow_feed: bool | None = None) -> int:
        """Feeds a feeder now (its portion when no amount is given); returns the eighths fed."""
        amount = self.portion(api_name) if eighths is None else eighths
        await self.data.feeders[api_name].device.feed(amount, slow_feed, False)
        await self.async_request_refresh()
        return amount
