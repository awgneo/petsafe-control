"""Tests for signing in: an email, the code PetSafe emails, then the devices to add."""

from unittest.mock import patch

import httpx
from fakes import CODE, EVA, LITTERBOX, SHILOH
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.petsafe.const import DOMAIN


async def test_sign_in(hass, cloud, cognito) -> None:
    """Signing in through Home Assistant's shared HTTP client (a new one would block the event loop) stores the tokens."""
    shared = httpx.AsyncClient(transport=cloud.transport)
    with (
        patch("custom_components.petsafe.config_flow.get_async_client", return_value=shared) as get_client,
        patch("custom_components.petsafe.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"email": "me@example.com"})
        assert result["step_id"] == "code"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "000000"})
        assert result["errors"] == {"code": "invalid_code"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": CODE})
        assert result["step_id"] == "devices"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"feeders": [EVA, SHILOH], "litterboxes": [LITTERBOX]}
        )
    get_client.assert_called_once_with(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "me@example.com"
    assert result["data"] == {
        "email": "me@example.com",
        "feeders": [EVA, SHILOH],
        "litterboxes": [LITTERBOX],
        "token": "id-signed-in",
        "access_token": "access-signed-in",
        "refresh_token": "refresh-signed-in",
    }
