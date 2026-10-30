"""Feeding for assistants: PetSafe's LLM tools platform, adding a tool to Assist's that feeds a pet by name."""

from __future__ import annotations

import re

import probatio
import voluptuous as vol
from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import llm

from .const import DOMAIN, EIGHTHS_PER_CUP, MAX_EIGHTHS, MIN_EIGHTHS
from .coordinator import PetSafeCoordinator

ALL = "all"

PROMPT = (
    "PetSafe feeders are named after the pet they feed. To feed a pet, use petsafe__FeedPet with its name (or 'all' for "
    "every pet); give cups only for an amount other than the pet's usual portion, such as a snack."
)


@callback
def feeders_by_name(hass: HomeAssistant) -> dict[str, tuple[PetSafeCoordinator, str]]:
    """Every loaded feeder by its device's name in Home Assistant: its coordinator and PetSafe name."""
    device_registry = dr.async_get(hass)
    feeders = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        coordinator: PetSafeCoordinator = entry.runtime_data
        for api_name, feeder in coordinator.data.feeders.items():
            device = device_registry.async_get_device_by_identifier((DOMAIN, api_name), entry.entry_id)
            name = (device.name_by_user or device.name) if device else None
            feeders[name or feeder.device.friendly_name] = (coordinator, api_name)
    return feeders


class FeedPetTool(llm.Tool):
    """Feeds a pet by name, or every pet: its usual portion, or the cups given."""

    # Prefixed with the domain, as Home Assistant requires of a platform's tools
    name = f"{DOMAIN}__FeedPet"
    title = "Feed a pet"
    description = (
        "Feeds a pet now from its PetSafe feeder. Feeders are named after their pet (e.g. 'Eva Feeder' feeds Eva). "
        "Without cups, each pet gets its usual portion; give cups for another amount, such as a snack "
        "(in eighths of a cup, up to 4 cups)."
    )
    parameters = probatio.Schema(
        {
            probatio.Required(
                "pet", description="The pet's name, as in its feeder's name, or 'all' for every pet."
            ): cv.string,
            probatio.Optional(
                "cups", description="How much to feed, in cups (1/8 to 4). Leave it out for the usual portion."
            ): vol.Coerce(float),
        }
    )
    annotations = llm.ToolAnnotations(read_only=False, destructive=False, idempotent=False, open_world=True)
    integration = DOMAIN

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> llm.ToolResult:
        """Feed the pet (or every pet)."""
        args = self.parameters(tool_input.tool_args)
        feeders = feeders_by_name(hass)
        if not feeders:
            return llm.ToolResult(data={"error": "No PetSafe feeder is set up"}, error=True)

        pet = args["pet"].strip()
        if pet.lower() == ALL:
            chosen = feeders
        else:
            word = re.compile(rf"\b{re.escape(pet)}\b", re.IGNORECASE)
            chosen = {name: feeder for name, feeder in feeders.items() if word.search(name)}
        if not chosen:
            return llm.ToolResult(
                data={"error": f"No feeder is named after '{pet}'", "feeders": sorted(feeders)}, error=True
            )

        eighths = None
        if "cups" in args:
            eighths = round(args["cups"] * EIGHTHS_PER_CUP)
            if not MIN_EIGHTHS <= eighths <= MAX_EIGHTHS:
                return llm.ToolResult(
                    data={"error": f"A feeder gives 1/8 to {MAX_EIGHTHS // EIGHTHS_PER_CUP} cups at a time"},
                    error=True,
                )

        fed = []
        for name, (coordinator, api_name) in sorted(chosen.items()):
            amount = await coordinator.async_feed(api_name, eighths)
            fed.append({"feeder": name, "cups": amount / EIGHTHS_PER_CUP})
        return llm.ToolResult(data={"fed": fed})


@callback
def async_get_tools(hass: HomeAssistant, llm_context: llm.LLMContext, api_id: str) -> LLMTools | None:
    """FeedPet, among Assist's tools (what an MCP server or a conversation agent offers), while a feeder is set up."""
    if api_id != llm.LLM_API_ASSIST or not feeders_by_name(hass):
        return None
    return LLMTools(tools=[FeedPetTool()], prompt=PROMPT)
