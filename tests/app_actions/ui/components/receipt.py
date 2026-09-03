"""App Actions for the success receipt modal (Feature Specification 2.4)."""

from __future__ import annotations

from dataclasses import dataclass

from tests.app_actions.ui.base_actions import BaseActions
from tests.app_actions.ui.locators import ReceiptLocators


@dataclass(frozen=True)
class Receipt:
    """The seven fields specification 2.4 requires on the receipt."""

    bet_id: str
    match: str
    selection: str
    stake: str
    odds: str
    payout: str
    timestamp: str

    def missing_fields(self) -> list[str]:
        """Named fields that came back empty, for a failure message that says which."""
        return [
            name
            for name, value in (
                ("bet id", self.bet_id),
                ("match", self.match),
                ("selection", self.selection),
                ("stake", self.stake),
                ("odds", self.odds),
                ("payout", self.payout),
                ("timestamp", self.timestamp),
            )
            if not value
        ]


class ReceiptActions(BaseActions):
    def is_visible(self) -> bool:
        return self.is_present(ReceiptLocators.MODAL)

    def read(self) -> Receipt:
        # Every field carries its own document-wide unique id in the real
        # markup, so each is queried directly rather than scoped under MODAL -
        # MODAL itself resolves to the bet-id element, which has no children.
        self.wait_for_visible(ReceiptLocators.MODAL)
        return Receipt(
            bet_id=self.text_of(ReceiptLocators.BET_ID),
            match=self.text_of(ReceiptLocators.MATCH),
            selection=self.text_of(ReceiptLocators.SELECTION),
            stake=self.text_of(ReceiptLocators.STAKE),
            odds=self.text_of(ReceiptLocators.ODDS),
            payout=self.text_of(ReceiptLocators.PAYOUT),
            timestamp=self.text_of(ReceiptLocators.TIMESTAMP),
        )

    def close(self) -> None:
        self.click(ReceiptLocators.CLOSE_BUTTON)
        self.wait_for_absent(ReceiptLocators.MODAL)
