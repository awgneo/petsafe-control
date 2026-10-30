"""Tests for FeedPet, the tool PetSafe adds to Assist's (what Claude reaches through Home Assistant's MCP server)."""

import probatio
from fakes import EVA, SHILOH
from homeassistant.core import Context
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from custom_components.petsafe.const import DOMAIN

CONTEXT = llm.LLMContext(platform="mcp_server", context=Context(), language="en", assistant="conversation", device_id=None)


async def assist(hass) -> llm.APIInstance:
    """Assist's API, as an MCP server serving all LLM APIs gets it."""
    assert await async_setup_component(hass, "llm", {})
    return await llm.async_get_api(hass, [api.id for api in llm.async_get_apis(hass)], CONTEXT)


async def feed_pet(hass, **args) -> llm.ToolResult:
    """Calls FeedPet as an assistant does."""
    return await (await assist(hass)).async_call_tool(llm.ToolInput(tool_name="petsafe__FeedPet", tool_args=args))


async def test_offered_among_assists_tools(hass, setup) -> None:
    """FeedPet joins Assist's tools, its parameters described as JSON schema; PetSafe adds no API of its own, which
    would namespace every tool's name (as merged APIs' are) and leave assistants calling names that no longer exist."""
    api = await assist(hass)
    assert [api.id for api in llm.async_get_apis(hass)] == [llm.LLM_API_ASSIST]
    (tool,) = [tool for tool in api.tools if tool.name == "petsafe__FeedPet"]
    assert "llm__GetDateTime" in [tool.name for tool in api.tools]
    schema = probatio.to_openapi(tool.parameters, custom_serializer=llm.selector_serializer, openapi_version="3.1.0")
    assert schema["properties"]["pet"]["type"] == "string"
    assert schema["properties"]["cups"]["type"] == "number"
    assert schema["required"] == ["pet"]
    assert "petsafe__FeedPet" in api.api_prompt


async def test_not_offered_without_feeders(hass) -> None:
    """Without a feeder set up, Assist has no FeedPet."""
    assert "petsafe__FeedPet" not in [tool.name for tool in (await assist(hass)).tools]


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
