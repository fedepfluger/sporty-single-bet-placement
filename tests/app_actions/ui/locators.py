"""The single place where the suite knows anything about the DOM.

Verified 2026-09-03 against the real application (no `data-testid` attributes
exist anywhere on the page - confirmed via `document.querySelectorAll('[data-testid]')`
returning zero elements). The app instead ships stable, predictable `id`
attributes on almost every interactive element (`bet-slip-stake-input`,
`odds-{matchId}-{selection}`, `modal-success-bet-id`, ...), which is what these
locators target directly. A short text/class fallback is kept only where no
`id` exists, as defence against a future markup tweak.
"""

from __future__ import annotations

from selenium.webdriver.common.by import By

Candidates = list[tuple[str, str]]

#: The 1 / X / 2 buttons of section 2.1, keyed by the API selection they submit.
#: Each odds button carries its label and its price in two separate spans
#: (`.oddsButtonLabel`, `.oddsButtonValue`), so the label is never mixed into
#: the price text the way a naive "read the whole button" approach would.
ODDS_BUTTON_LABEL = {"HOME": "1", "DRAW": "X", "AWAY": "2"}


class MatchListLocators:
    MATCH_CARD: Candidates = [(By.CSS_SELECTOR, "div.matchCard")]
    HOME_TEAM: Candidates = [(By.CSS_SELECTOR, ".teamRow:nth-of-type(1) .teamName")]
    AWAY_TEAM: Candidates = [(By.CSS_SELECTOR, ".teamRow:nth-of-type(2) .teamName")]
    #: Last child of `.matchMeta`: a badge ("PAST") only precedes it for
    #: fixtures that have already kicked off (see docs/02, BUG-011).
    KICKOFF: Candidates = [(By.CSS_SELECTOR, ".matchMeta span:last-child")]
    #: PAST / TODAY / UPCOMING - see docs/02, BUG-024.
    STATUS_BADGE: Candidates = [(By.CSS_SELECTOR, ".matchMeta .badge")]
    ODDS_BUTTONS: Candidates = [(By.CSS_SELECTOR, "button.oddsButton")]
    ODDS_BUTTON_PRICE: Candidates = [(By.CSS_SELECTOR, ".oddsButtonValue")]

    @staticmethod
    def odds_button(selection: str) -> Candidates:
        """`selection` is HOME / DRAW / AWAY, rendered as the 1 / X / 2 buttons."""
        label = ODDS_BUTTON_LABEL[selection.upper()]
        return [(By.XPATH, f".//button[contains(@class,'oddsButton')][.//*[normalize-space(text())='{label}']]")]


class BetSlipLocators:
    SELECTION: Candidates = [(By.CSS_SELECTOR, ".betSelectionTeams")]
    #: Reads e.g. "Match Winner: Home" - the outcome actually backed, distinct
    #: from SELECTION (the match name).
    SELECTION_MARKET: Candidates = [(By.CSS_SELECTOR, ".betSelectionMarket")]
    STAKE_INPUT: Candidates = [(By.CSS_SELECTOR, "#bet-slip-stake-input")]
    BALANCE: Candidates = [(By.CSS_SELECTOR, "#bet-slip-balance")]
    POTENTIAL_PAYOUT: Candidates = [(By.CSS_SELECTOR, "#bet-slip-potential-payout")]
    PLACE_BET_BUTTON: Candidates = [(By.CSS_SELECTOR, "#bet-slip-place-bet")]
    REMOVE_ALL_BUTTON: Candidates = [(By.CSS_SELECTOR, "#bet-slip-remove-all")]
    REMOVE_SELECTION_BUTTON: Candidates = [(By.CSS_SELECTOR, "#bet-slip-selection-remove")]
    #: Not `role="alert"` in the real markup - a plain warning block next to the
    #: stake input, present only while the current stake is invalid.
    VALIDATION_MESSAGE: Candidates = [(By.CSS_SELECTOR, ".stakeWarning")]
    EMPTY_STATE: Candidates = [(By.CSS_SELECTOR, ".betSlipBodyEmpty")]


class HeaderLocators:
    #: No id or class on the real element - it is the only "Balance: €..."
    #: text node outside the bet slip, so it is matched by content instead.
    BALANCE: Candidates = [
        (By.XPATH, "//header//*[starts-with(normalize-space(text()), 'Balance:')]"),
        (By.XPATH, "(//*[starts-with(normalize-space(text()), 'Balance:')])[1]"),
    ]


class ReceiptLocators:
    #: `.modalPanel` is a shared wrapper class (the error modal likely reuses
    #: it too), so "is the SUCCESS modal open" is asked via a field only the
    #: success modal has, not the generic panel class.
    MODAL: Candidates = [(By.CSS_SELECTOR, "#modal-success-bet-id")]
    BET_ID: Candidates = [(By.CSS_SELECTOR, "#modal-success-bet-id")]
    MATCH: Candidates = [(By.CSS_SELECTOR, "#modal-success-match")]
    #: Not present in the real receipt - see docs/02, BUG-010. Kept so a fix
    #: is picked up automatically instead of requiring a locator change too.
    SELECTION: Candidates = [(By.CSS_SELECTOR, "#modal-success-selection")]
    STAKE: Candidates = [(By.CSS_SELECTOR, "#modal-success-stake")]
    ODDS: Candidates = [(By.CSS_SELECTOR, "#modal-success-odds")]
    PAYOUT: Candidates = [(By.CSS_SELECTOR, "#modal-success-payout")]
    TIMESTAMP: Candidates = [(By.CSS_SELECTOR, "#modal-success-placed-at")]
    CLOSE_BUTTON: Candidates = [(By.CSS_SELECTOR, "#modal-success-close")]


class ErrorModalLocators:
    #: Never observed live (no reproducible client-triggered failure was found
    #: in the time available - the backend answers 200 far more often than the
    #: spec's error classes suggest, see docs/02 section 3). Guessed from the
    #: success modal's `modal-success-*` naming convention; verify on next pass.
    MODAL: Candidates = [(By.CSS_SELECTOR, "#modal-error-title, .modalPanel .modalErrorIcon")]
    TITLE: Candidates = [(By.CSS_SELECTOR, "#modal-error-title")]
    BODY: Candidates = [(By.CSS_SELECTOR, "#modal-error-body")]
    REBET_BUTTON: Candidates = [(By.CSS_SELECTOR, "#modal-error-rebet")]
    CLOSE_BUTTON: Candidates = [(By.CSS_SELECTOR, "#modal-error-close")]
    DISMISS_X: Candidates = [(By.CSS_SELECTOR, "#modal-error-close-x")]


class FilterLocators:
    ODDS_TOGGLE: Candidates = [(By.XPATH, "//button[contains(., 'Odds:')]")]
    ODDS_POPOVER: Candidates = [(By.CSS_SELECTOR, "#odds-filter-popover")]
    #: No ids on the real inputs - scoped within the popover by their label.
    ODDS_MIN: Candidates = [(By.XPATH, "//*[@id='odds-filter-popover']//label[.='Min']/following-sibling::input")]
    ODDS_MAX: Candidates = [(By.XPATH, "//*[@id='odds-filter-popover']//label[.='Max']/following-sibling::input")]
    ODDS_APPLY: Candidates = [(By.XPATH, "//*[@id='odds-filter-popover']//button[normalize-space(.)='Apply']")]
    #: No dedicated error element was observed for an inverted odds range in
    #: the time available; not yet verified live.
    ERROR: Candidates = [(By.CSS_SELECTOR, "[role='alert']"), (By.CSS_SELECTOR, "[class*='error' i]")]
