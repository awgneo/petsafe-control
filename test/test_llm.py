"""Tests for FeedPet, the tool assistants (Claude, through Home Assistant's MCP server) feed with."""

import probatio
from fakes import EVA, SHILOH
from homeassistant.core import Context
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import llm

from custom_components.petsafe.const import DOMAIN


async def feed_pet(hass, **args):
    """Calls FeedPet as an assistant does, through every LLM API merged (the MCP server's All LLM APIs)."""
    context = llm.LLMContext(platform="mcp_server", context=Context(), language="en", assistant="conversation", device_id=None)
    api = await llm.async_get_api(hass, [api.id for api in llm.async_get_apis(hass)], context)
    # Merged with other APIs, its name is namespaced (petsafe_control__FeedPet)
    (name,) = [tool.name for tool in api.tools if tool.name.endswith("FeedPet")]
    return await api.async_call_tool(llm.ToolInput(tool_name=name, tool_args=args))


async def test_offered_to_assistants(hass, setup) -> None:
    """The MCP server's merged APIs offer FeedPet, its parameters described as JSON schema."""
    context = llm.LLMContext(platform="mcp_server", context=Context(), language="en", assistant="conversation", device_id=None)
    api = await llm.async_get_api(hass, DOMAIN, context)
    (tool,) = api.tools
    schema = probatio.to_openapi(tool.parameters, custom_serializer=llm.selector_serializer, openapi_version="3.1.0")
    assert schema["properties"]["pet"]["type"] == "string"
    assert schema["properties"]["cups"]["type"] == "number"
    assert schema["required"] == ["pet"]


async def test_feed_the_dogs(hass, cloud, setup) -> None:
    """'all' feeds every pet its portion."""
    result = await feed_pet(hass, pet="all")
    assert not result.error
    assert cloud.meals() == [(EVA, 24), (SHILOH, 8)]
    assert result.data == {"fed": [{"feeder": "Eva Feeder", "cups": 3.0}, {"feeder": "Shiloh Feeder", "cups": 1.0}]}


async def test_feed_one_a_snack(hass, cloud, setup) -> None:
    """A pet by name, any case, the cups given; the portion stays."""
    result = await feed_pet(hass, pet="shiloh", cups=0.5)
    assert result.data == {"fed": [{"feeder": "Shiloh Feeder", "cups": 0.5}]}
    assert cloud.meals() == [(SHILOH, 4)]
    assert hass.states.get("number.shiloh_feeder_portion").state == "1.0"


async def test_feeder_renamed_in_home_assistant(hass, cloud, setup) -> None:
    """The name a feeder has in Home Assistant is the one matched."""
    devices = dr.async_get(hass)
    device = devices.async_get_device_by_identifier((DOMAIN, EVA), setup.entry_id)
    devices.async_update_device(device.id, name_by_user="Meditation Room Eva Feeder")
    result = await feed_pet(hass, pet="Eva")
    assert result.data == {"fed": [{"feeder": "Meditation Room Eva Feeder", "cups": 3.0}]}


async def test_unknown_pet(hass, cloud, setup) -> None:
    """A pet no feeder is named after: nothing fed, and the feeders listed for another try."""
    result = await feed_pet(hass, pet="Rex")
    assert result.error
    assert result.data["feeders"] == ["Eva Feeder", "Shiloh Feeder"]
    assert cloud.meals() == []


async def test_amounts_a_feeder_cannot_give(hass, cloud, setup) -> None:
    """More than 4 cups, or less than 1/8, is refused rather than changed."""
    assert (await feed_pet(hass, pet="Eva", cups=5)).error
    assert (await feed_pet(hass, pet="Eva", cups=0.01)).error
    assert cloud.meals() == []
