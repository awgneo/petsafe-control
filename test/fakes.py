"""A fake PetSafe cloud: its API answered from memory through httpx, and Cognito's token refresh."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

import httpx

from custom_components.petsafe.petsafe_api.const import PETSAFE_API_BASE

EVA = "eva-thing"
SHILOH = "shiloh-thing"
LITTERBOX = "box-thing"

# 2026-10-26 14:21:10 UTC and the days before: the feedings PetSafe lists, oldest first
NOON = 1793024470


def feeder(thing_name: str, name: str, **settings: Any) -> dict[str, Any]:
    """A Smart Feed 2.0 on its adapter (no batteries), full of food, as PetSafe describes it."""
    return {
        "id": thing_name.upper(),
        "thing_name": thing_name,
        "battery_voltage": "90",
        "is_batteries_installed": False,
        "is_food_low": 0,
        "food_sensor_current": 0,
        "firmware_version": "V2.2.0",
        "product_name": "SmartFeed_2.0",
        "network_rssi": -62,
        "settings": {
            "friendly_name": name,
            "paused": False,
            "slow_feed": False,
            "child_lock": False,
            "timezone": "America/New_York",
            **settings,
        },
    }


def feeding(amount: int, at: int) -> dict[str, Any]:
    """A feeding's message."""
    return {"message_type": "FEED_DONE", "payload": {"amount": amount, "time": at, "source": "cloud"}}


class FakeCloud:
    """PetSafe's API for one account: Eva's and Shiloh's feeders and a litter box, and what's sent to it."""

    def __init__(self) -> None:
        self.feeders = {
            EVA: feeder(EVA, "Eva Feeder", paused=True),
            SHILOH: feeder(SHILOH, "Shiloh Feeder"),
        }
        self.messages = {
            EVA: [feeding(24, NOON - 172800), {"message_type": "FOOD_LOW", "payload": {}}, feeding(24, NOON)],
            SHILOH: [feeding(8, NOON - 172800), feeding(6, NOON - 86400), feeding(8, NOON)],
        }
        self.schedules: dict[str, list[dict[str, Any]]] = {
            EVA: [],
            SHILOH: [{"id": 11, "time": "08:00", "amount": 8}, {"id": 12, "time": "18:00", "amount": 8}],
        }
        self.litterboxes = [
            {
                "thingName": LITTERBOX,
                "friendlyName": "Litter Box",
                "productName": "ScoopFree",
                "shadow": {"state": {"reported": {"firmware": "1.0", "rakeCount": 7, "rssi": -55, "rakeDelayTime": 15}}},
            }
        ]
        self.activity = [
            {"payload": {"code": "RAKE_FINISHED", "timestamp": str((NOON - 3600) * 1000)}},
            {"payload": {"code": "CAT_IN_BOX", "timestamp": str(NOON * 1000)}},
        ]
        # (method, path, JSON body) for each request that changes something
        self.sent: list[tuple[str, str, Any]] = []
        self.transport = httpx.MockTransport(self.handle)

    def meals(self) -> list[tuple[str, int]]:
        """(feeder, eighths) for each feeding sent."""
        return [
            (path.split("/")[2], body["amount"]) for method, path, body in self.sent if path.endswith("/meals")
        ]

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Answer a request as PetSafe does."""
        path = request.url.path.removeprefix(httpx.URL(PETSAFE_API_BASE).path)
        body = json.loads(request.content) if request.content else None
        if request.method != "GET":
            self.sent.append((request.method, path, body))

        if path == "smart-feed/feeders":
            return httpx.Response(200, json=list(copy.deepcopy(self.feeders).values()))
        if path == "scoopfree/product/product":
            return httpx.Response(200, json={"data": copy.deepcopy(self.litterboxes)})
        if match := re.fullmatch(r"smart-feed/feeders/([^/]+)/(.*)", path):
            return self.feeder_request(request.method, match[1], match[2], body)
        if match := re.fullmatch(r"scoopfree/product/product/([^/]+)/(.*)", path):
            if match[2] == "activity":
                return httpx.Response(200, json={"data": self.activity})
            return httpx.Response(200, json={})
        return httpx.Response(404)

    def feeder_request(self, method: str, thing: str, rest: str, body: Any) -> httpx.Response:
        """A request about one feeder."""
        if rest == "":
            return httpx.Response(200, json=self.feeders[thing])
        if rest == "messages":
            return httpx.Response(200, json=self.messages[thing])
        if rest == "schedules" and method == "GET":
            return httpx.Response(200, json=self.schedules[thing])
        if rest == "schedules" and method == "POST":
            self.schedules[thing].append({"id": 99, **body})
            return httpx.Response(200, json={"id": 99})
        if rest == "schedules" and method == "DELETE":
            self.schedules[thing] = []
        if match := re.fullmatch(r"schedules/(\d+)", rest):
            schedule = next(s for s in self.schedules[thing] if s["id"] == int(match[1]))
            if method == "PUT":
                schedule.update(body)
            else:
                self.schedules[thing].remove(schedule)
        if match := re.fullmatch(r"settings/(\w+)", rest):
            self.feeders[thing]["settings"][match[1]] = body["value"]
        return httpx.Response(200, json={})


# The code PetSafe emails
CODE = "123456"


class FakeCognito:
    """Cognito's sign-in by emailed code, and its token refresh: every refresh is counted, tokens last an hour."""

    def __init__(self) -> None:
        self.refreshes = 0

    def initiate_auth(self, **kwargs: Any) -> dict[str, Any]:
        """Start a sign-in (a code is emailed), or refresh the tokens."""
        if kwargs["AuthFlow"] == "CUSTOM_AUTH":
            return {
                "ChallengeName": "CUSTOM_CHALLENGE",
                "Session": "session",
                "ChallengeParameters": {"USERNAME": kwargs["AuthParameters"]["USERNAME"]},
            }
        assert kwargs["AuthFlow"] == "REFRESH_TOKEN_AUTH"
        self.refreshes += 1
        return {
            "AuthenticationResult": {
                "IdToken": f"id-{self.refreshes}",
                "AccessToken": f"access-{self.refreshes}",
                "ExpiresIn": 3600,
            }
        }

    def respond_to_auth_challenge(self, **kwargs: Any) -> dict[str, Any]:
        """Answer the emailed code: tokens when it's right, another challenge when it isn't."""
        if kwargs["ChallengeResponses"]["ANSWER"] != CODE:
            return {"ChallengeName": "CUSTOM_CHALLENGE", "Session": "session"}
        return {
            "AuthenticationResult": {
                "IdToken": "id-signed-in",
                "AccessToken": "access-signed-in",
                "RefreshToken": "refresh-signed-in",
                "ExpiresIn": 3600,
            }
        }
