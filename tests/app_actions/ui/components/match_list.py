"""App Actions for the match catalogue (Feature Specification 2.1)."""

from __future__ import annotations

from decimal import Decimal

from selenium.webdriver.remote.webelement import WebElement

from tests.app_actions.ui.base_actions import BaseActions
from tests.app_actions.ui.locators import BetSlipLocators, MatchListLocators
from tests.support.assertions import to_money
from tests.support.reporting import log


class MatchListActions(BaseActions):
    def cards(self) -> list[WebElement]:
        return self.find_all(MatchListLocators.MATCH_CARD)

    def count(self) -> int:
        return len(self.cards())

    def card(self, index: int = 0) -> WebElement:
        cards = self.cards()
        assert len(cards) > index, f"Expected at least {index + 1} matches, the list shows {len(cards)}"
        return cards[index]

    def title(self, index: int = 0) -> str:
        card = self.card(index)
        home = self.text_of(MatchListLocators.HOME_TEAM, context=card)
        away = self.text_of(MatchListLocators.AWAY_TEAM, context=card)
        if home and away:
            return f"{home} vs {away}"
        return card.text.strip().splitlines()[0] if card.text.strip() else ""

    def kickoff(self, index: int = 0) -> str:
        """The kickoff date/time label specification 2.1 requires on every card."""
        return self.text_of(MatchListLocators.KICKOFF, context=self.card(index))

    def status_badge(self, index: int = 0) -> str:
        """The card's status text: "PAST", "TODAY" or "UPCOMING".

        The badge is always present (see docs/02, BUG-011) - it is the text
        that changes, not the element's existence. "TODAY" is a real third
        value the frontend computes for a fixture whose `kickoffDate` is
        today (see docs/02, BUG-024) - `kickoffDate` carries no time, so
        "today" cannot be told apart from "already kicked off".
        """
        return self.text_of(MatchListLocators.STATUS_BADGE, context=self.card(index)).strip().upper()

    def first_upcoming_index(self) -> int:
        """Index of the first card that is unambiguously in the future.

        The real catalogue lists past fixtures before upcoming ones (BUG-011),
        so a test that blindly bets on card 0 bets on a match already decided.
        Checked as "badge says UPCOMING", not "badge does not say PAST": a
        default-deny check, so a fixture badged "TODAY" (BUG-024) is treated
        as not safely bettable rather than assumed fine. Mirrors
        `BettingApiActions.first_match()`'s API-side fix.
        """
        for index in range(self.count()):
            if self.status_badge(index) == "UPCOMING":
                return index
        raise AssertionError(f"No upcoming match found among {self.count()} cards.")

    def odds_value(self, selection: str, index: int | None = None) -> Decimal:
        """The decimal price on a 1 / X / 2 button.

        Label and price are two separate spans in the real markup
        (`.oddsButtonLabel`, `.oddsButtonValue`), so the price never needs to be
        parsed out of a combined string. Defaults to whichever card
        `select_odds`/`select_upcoming_odds` last clicked, since asking for
        "the odds" right after making a selection almost always means that one.
        """
        if index is None:
            index = getattr(self, "_last_selected_index", 0)
        button = self.find(MatchListLocators.odds_button(selection), context=self.card(index))
        price = self.find(MatchListLocators.ODDS_BUTTON_PRICE, context=button)
        return to_money(price.text)

    def select_upcoming_odds(self, selection: str) -> int:
        """Select an outcome on the first bettable match, skipping past fixtures.

        Use this instead of `select_odds(selection)` whenever the test is going
        to place the bet - see `first_upcoming_index` for why index 0 is not
        safe to assume in the real catalogue.
        """
        index = self.first_upcoming_index()
        self.select_odds(selection, index=index)
        return index

    def select_odds(self, selection: str, index: int = 0) -> None:
        """Click the 1 / X / 2 button for a match; a new click replaces the old selection."""
        card = self.card(index)
        self.click(MatchListLocators.odds_button(selection), context=card)
        # The slip rendering its Place Bet button is the signal the click landed.
        self.wait_for_visible(BetSlipLocators.PLACE_BET_BUTTON)
        self._last_selected_index = index
        log(f"Selected {selection.upper()} on match #{index}", name="UI action")

    def active_odds_buttons(self) -> list[WebElement]:
        """Every odds button currently rendered as active - used to prove only one survives."""
        return [
            button
            for button in self.find_all(MatchListLocators.ODDS_BUTTONS)
            if "oddsButtonSelected" in (button.get_attribute("class") or "")
        ]
