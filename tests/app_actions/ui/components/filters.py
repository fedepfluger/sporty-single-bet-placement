"""App Actions for the odds filter (Feature Specification 2.6).

A popover opened from a toggle button in the toolbar, not an inline field - a
different shape than first assumed, confirmed by inspecting the real markup.

The date filter exists in the same toolbar (also a popover, a single-day
calendar picker rather than two date fields) but is not implemented here: its
opening state was inspected, but the inclusive-range interaction - does a
second calendar click set the end of the range, or is there a separate
control? - was never driven end to end, so there is nothing here to claim as
verified. See docs/02.
"""

from __future__ import annotations

from tests.app_actions.ui.base_actions import BaseActions
from tests.app_actions.ui.locators import FilterLocators


class FilterActions(BaseActions):
    def by_odds(self, minimum: str, maximum: str) -> None:
        self.click(FilterLocators.ODDS_TOGGLE)
        self.wait_for_visible(FilterLocators.ODDS_POPOVER)
        self.type_text(FilterLocators.ODDS_MIN, minimum)
        self.type_text(FilterLocators.ODDS_MAX, maximum)
        self.click(FilterLocators.ODDS_APPLY)

    def error(self) -> str:
        return self.text_of(FilterLocators.ERROR)
