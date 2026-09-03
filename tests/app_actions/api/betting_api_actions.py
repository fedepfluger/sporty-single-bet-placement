"""App Actions for the betting API.

An "action" is a business intent (`place_bet`, `reset_balance`, `pick_a_match`),
not an HTTP call. Steps and UI tests reuse these to arrange state, which is why
a UI scenario can set up its data through the API in one readable line.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import requests

from config.endpoints import Endpoint
from config.settings import get_settings
from tests.app_actions.api.http_client import ApiClient
from tests.support.assertions import to_money


class BettingApiActions:
    def __init__(self, client: ApiClient | None = None) -> None:
        self.client = client or ApiClient()
        self.settings = get_settings()

    # --- reads -----------------------------------------------------------
    def get_matches(self, params: dict[str, Any] | None = None) -> requests.Response:
        return self.client.get(Endpoint.MATCHES, params=params)

    def get_balance(self, params: dict[str, Any] | None = None) -> requests.Response:
        return self.client.get(Endpoint.BALANCE, params=params)

    def read_balance(self) -> Decimal:
        response = self.get_balance()
        assert response.status_code == 200, f"Could not read the balance: HTTP {response.status_code}"
        return to_money(response.json()["balance"])

    def list_matches(self) -> list[dict[str, Any]]:
        response = self.get_matches()
        assert response.status_code == 200, f"Could not read the match list: HTTP {response.status_code}"
        return response.json()

    def first_match(self) -> dict[str, Any]:
        """The first bettable, unambiguously-in-the-future fixture in the catalogue.

        The real catalogue is not sorted upcoming-first: it returns past
        fixtures before future ones, so index 0 is routinely a match that has
        already kicked off (see docs/02, BUG-011). Filtering here, once, keeps
        every test that arranges a bet through this method pointed at a
        fixture the API will actually accept.

        `kickoffDate` is a date with no time component, so a fixture dated
        today cannot be told apart from one already in progress - the real
        frontend's own status logic gives "today" a third bucket distinct
        from both "past" and "upcoming" for exactly this reason (see docs/02,
        BUG-024). The comparison is strictly `>`, not `>=`, so today's
        fixtures are excluded rather than assumed safe.
        """
        matches = self.list_matches()
        assert matches, "The match catalogue is empty; no bet can be placed."
        today = date.today().isoformat()
        upcoming = [m for m in matches if m["kickoffDate"][:10] > today]
        assert upcoming, f"No unambiguously upcoming fixture found in a catalogue of {len(matches)} matches."
        return upcoming[0]

    def odds_for(self, match: dict[str, Any], selection: str) -> Decimal:
        key = {"HOME": "home", "DRAW": "draw", "AWAY": "away"}[selection.upper()]
        return to_money(match["odds"][key])

    # --- writes ----------------------------------------------------------
    def place_bet(
        self,
        match_id: str | None,
        selection: str | None,
        stake: Any,
        extra_fields: dict[str, Any] | None = None,
    ) -> requests.Response:
        body: dict[str, Any] = {"matchId": match_id, "selection": selection, "stake": stake}
        if extra_fields:
            body.update(extra_fields)
        return self.client.post(Endpoint.PLACE_BET, json_body=body)

    def place_bet_with_body(self, body: Any) -> requests.Response:
        """Send an arbitrary (possibly invalid) body - used by the protocol matrix."""
        return self.client.post(Endpoint.PLACE_BET, json_body=body)

    def place_bet_with_raw_body(self, raw: str, content_type: str | None = "application/json") -> requests.Response:
        return self.client.request("POST", Endpoint.PLACE_BET, raw_body=raw.encode("utf-8"), content_type=content_type)

    def reset_balance(self) -> requests.Response:
        return self.client.post(Endpoint.RESET_BALANCE, json_body={})

    def reset_balance_to_initial(self) -> Decimal:
        """Test data hygiene: bring the user back to a known balance before a scenario."""
        response = self.reset_balance()
        assert response.status_code == 200, f"Could not reset the balance: HTTP {response.status_code}"
        return to_money(response.json()["balance"])

    # --- protocol abuse --------------------------------------------------
    def call_with_method(self, endpoint: str, method: str, json_body: Any = None) -> requests.Response:
        return self.client.request(method.upper(), endpoint, json_body=json_body)
