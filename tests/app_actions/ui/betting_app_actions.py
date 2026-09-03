"""The entry point for every UI test: one page, composed of its components.

App Actions, not page objects: the public methods are things a punter does, and
each one owns its own waiting. A test never touches a locator or a WebDriverWait.

This class deliberately holds almost no behaviour of its own. Anything belonging
to a single region of the screen lives in `components/`; what stays here is the
page-level chrome and the flows that genuinely span more than one component -
`place_bet_and_wait()` starts in the bet slip and ends in either the receipt or
the error modal, so it belongs to neither.
"""

from __future__ import annotations

from decimal import Decimal

from selenium.webdriver.remote.webdriver import WebDriver

from tests.app_actions.ui.base_actions import BaseActions
from tests.app_actions.ui.components.bet_slip import BetSlipActions
from tests.app_actions.ui.components.error_modal import ErrorModalActions
from tests.app_actions.ui.components.filters import FilterActions
from tests.app_actions.ui.components.match_list import MatchListActions
from tests.app_actions.ui.components.receipt import ReceiptActions
from tests.app_actions.ui.locators import HeaderLocators, MatchListLocators
from tests.support.assertions import to_money
from tests.support.reporting import log

SUCCESS = "success"
FAILURE = "failure"


class BettingAppActions(BaseActions):
    def __init__(self, driver: WebDriver) -> None:
        super().__init__(driver)
        self.matches = MatchListActions(driver)
        self.slip = BetSlipActions(driver)
        self.receipt = ReceiptActions(driver)
        self.error_modal = ErrorModalActions(driver)
        self.filters = FilterActions(driver)

    # --- navigation ------------------------------------------------------
    def open_betting_page(self, user_id: str | None = None) -> BettingAppActions:
        self.driver.get(self.settings.ui_url(user_id))
        self.wait_for_visible(MatchListLocators.MATCH_CARD)
        log("Betting page loaded and the match list is rendered", name="UI action")
        return self

    # --- page chrome -----------------------------------------------------
    def header_balance(self) -> Decimal:
        """The balance in the header, which the spec says mirrors the bet slip."""
        return to_money(self.text_of(HeaderLocators.BALANCE))

    # --- cross-component flow --------------------------------------------
    def place_bet_and_wait(self, timeout: int | None = None) -> str:
        """Submit and block until the flow resolves. Returns 'success' or 'failure'.

        Specification 2.3 requires the in-progress state to always resolve to
        exactly one final outcome, so an unresolved slip fails here rather than
        turning into a flaky wait somewhere in a test.
        """
        self.slip.click_place_bet()
        outcome = self.wait_until(
            lambda _: (SUCCESS if self.receipt.is_visible() else FAILURE if self.error_modal.is_visible() else None),
            timeout=timeout,
            message="Bet placement never resolved to a receipt or an error modal",
        )
        log(f"Bet placement resolved as '{outcome}'", name="UI action")
        return outcome

    # --- diagnostics -----------------------------------------------------
    def browser_errors(self) -> list[str]:
        try:
            return [e["message"] for e in self.driver.get_log("browser") if e.get("level") == "SEVERE"]
        except Exception:  # noqa: BLE001 - log access is best-effort
            return []
