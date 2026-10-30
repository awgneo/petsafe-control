"""Tests for the PetSafe library's fixes: tokens refreshed once an hour, the newest feeding, repeating it."""

import httpx
from fakes import EVA, SHILOH, FakeCloud

from custom_components.petsafe.petsafe_api import PetSafeClient


def client(cloud: FakeCloud) -> PetSafeClient:
    """A client signed in as Home Assistant stores it: tokens without their expiry."""
    return PetSafeClient(
        "me@example.com", "id-0", "refresh-0", "access-0", client=httpx.AsyncClient(transport=cloud.transport)
    )


async def test_tokens_refresh_once_until_they_expire(cognito) -> None:
    """The first request refreshes the tokens; the next ones use them (they last an hour)."""
    api = client(FakeCloud())
    for _ in range(3):
        await api.get_feeders()
    assert cognito.refreshes == 1
    assert api.id_token == "id-1"


async def test_last_feeding_is_the_newest(cognito) -> None:
    """Messages come oldest first: the last feeding is the newest."""
    cloud = FakeCloud()
    feeders = {feeder.api_name: feeder for feeder in await client(cloud).get_feeders()}
    assert (await feeders[SHILOH].get_last_feeding())["payload"]["amount"] == 8
    cloud.messages[EVA] = []
    assert await feeders[EVA].get_last_feeding() is None


async def test_repeat_feed(cognito) -> None:
    """Repeating the last feeding gives its amount."""
    cloud = FakeCloud()
    feeders = {feeder.api_name: feeder for feeder in await client(cloud).get_feeders()}
    await feeders[EVA].repeat_feed()
    assert cloud.meals() == [(EVA, 24)]
