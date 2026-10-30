"""Test configuration: the integration set up against a fake PetSafe account."""

from collections.abc import Generator
from unittest.mock import patch

import httpx
import pytest
from fakes import EVA, SHILOH, FakeCloud, FakeCognito
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.petsafe.const import CONF_REFRESH_TOKEN, DOMAIN
from custom_components.petsafe.petsafe_api import PetSafeClient

# 2026-10-26 15:00 UTC (11:00 in New York): after the morning feedings, before the evening ones
NOW = "2026-10-26 15:00:00+00:00"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def cloud() -> FakeCloud:
    """The account's feeders and litter box."""
    return FakeCloud()


@pytest.fixture
def cognito() -> Generator[FakeCognito]:
    """Cognito, refreshing the client's tokens."""
    cognito = FakeCognito()

    async def client(self: PetSafeClient) -> FakeCognito:
        return cognito

    async def session(self: PetSafeClient) -> None:
        return None

    with (
        patch.object(PetSafeClient, "_PetSafeClient__get_cognito_client", client),
        patch.object(PetSafeClient, "_PetSafeClient__get_cognito_session", session),
    ):
        yield cognito


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """The account as its config flow stores it."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="me@example.com",
        data={
            "email": "me@example.com",
            "token": "id-0",
            "access_token": "access-0",
            CONF_REFRESH_TOKEN: "refresh-0",
            "feeders": [EVA, SHILOH],
            "litterboxes": [],
        },
    )


@pytest.fixture
async def setup(hass, freezer, cloud, cognito, mock_config_entry) -> MockConfigEntry:
    """Sets the integration up on the fake account, at NOW."""
    freezer.move_to(NOW)
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.petsafe.get_async_client", return_value=httpx.AsyncClient(transport=cloud.transport)):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry
