"""App Actions for the bet slip (Feature Specification 2.2 and 2.3)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from tests.app_actions.ui.base_actions import BaseActions
from tests.app_actions.ui.locators import BetSlipLocators
from tests.support.assertions import to_money
from tests.support.reporting import log


@dataclass(frozen=True)
class SlipState:
    """Everything the slip is showing, for a single readable failure message."""

    selection: str
    stake: str
    balance: str
    payout: str


class BetSlipActions(BaseActions):
    def enter_stake(self, stake: Any) -> None:
        self.type_text(BetSlipLocators.STAKE_INPUT, str(stake))
        log(f"Entered stake '{stake}'", name="UI action")

    def stake_value(self) -> str:
        return self.value_of(BetSlipLocators.STAKE_INPUT)

    def market(self) -> str:
        """The outcome actually backed, e.g. "Match Winner: Home"."""
        return self.text_of(BetSlipLocators.SELECTION_MARKET)

    def state(self) -> SlipState:
        return SlipState(
            selection=self.text_of(BetSlipLocators.SELECTION),
            stake=self.stake_value(),
            balance=self.text_of(BetSlipLocators.BALANCE),
            payout=self.text_of(BetSlipLocators.POTENTIAL_PAYOUT),
        )

    def potential_payout(self) -> Decimal:
        return to_money(self.text_of(BetSlipLocators.POTENTIAL_PAYOUT))

    def balance(self) -> Decimal:
        """The balance the slip's own header shows.

        Only rendered while the slip is empty - the moment a selection exists
        the header swaps this for a "Remove All" button instead (see docs/02,
        BUG-023). Callers that need the balance after selecting should read
        the page header instead.
        """
        return to_money(self.text_of(BetSlipLocators.BALANCE))

    def validation_message(self) -> str:
        return self.text_of(BetSlipLocators.VALIDATION_MESSAGE)

    def is_place_bet_enabled(self) -> bool:
        return self.find(BetSlipLocators.PLACE_BET_BUTTON).is_enabled()

    def is_empty(self) -> bool:
        return self.is_present(BetSlipLocators.EMPTY_STATE) or not self.is_present(BetSlipLocators.SELECTION)

    def click_place_bet(self) -> None:
        self.click(BetSlipLocators.PLACE_BET_BUTTON)

    def remove_selection(self) -> None:
        self.click(BetSlipLocators.REMOVE_SELECTION_BUTTON)

    def remove_all(self) -> None:
        self.click(BetSlipLocators.REMOVE_ALL_BUTTON)
