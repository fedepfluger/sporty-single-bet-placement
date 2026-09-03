"""The bet slip enforces the stake rules before any money moves.

The UI is the first line of defence. These tests assert the copy the
specification mandates in section 4.4, because a vague error is a support cost.
"""

from __future__ import annotations

import pytest

from tests.support.assertions import assert_payout

pytestmark = pytest.mark.ui


@pytest.fixture
def page(betting_page):
    """The betting page with HOME already selected on the first match."""
    betting_page.matches.select_upcoming_odds("HOME")
    return betting_page


@pytest.mark.regression
@pytest.mark.boundary
@pytest.mark.negative
@pytest.mark.parametrize("stake", ["0.99", "0.01", "0"])
def test_stakes_below_the_minimum_are_refused_with_the_documented_copy(page, stake):
    """TC_SBP_UI_V1 - specification 4.4 fixes the wording, not just the behaviour."""
    page.slip.enter_stake(stake)

    assert not page.slip.is_place_bet_enabled(), "Place Bet is enabled for a stake below the minimum."
    message = page.slip.validation_message()
    assert (
        "minimum stake is" in message.lower()
    ), f"Expected the documented minimum-stake copy, the UI shows {message!r}"


@pytest.mark.regression
@pytest.mark.boundary
@pytest.mark.negative
@pytest.mark.parametrize("stake", ["100.01", "500"])
def test_stakes_above_the_maximum_are_refused_with_the_documented_copy(page, stake):
    """TC_SBP_UI_V2 - the ceiling is a licensing limit, so the copy must be explicit."""
    page.slip.enter_stake(stake)

    assert not page.slip.is_place_bet_enabled(), "Place Bet is enabled for a stake above the maximum."
    message = page.slip.validation_message()
    assert (
        "maximum stake is" in message.lower()
    ), f"Expected the documented maximum-stake copy, the UI shows {message!r}"


@pytest.mark.regression
@pytest.mark.boundary
@pytest.mark.spec_gap
@pytest.mark.parametrize("stake", ["1.00", "100.00"])
def test_the_documented_boundaries_themselves_are_accepted(page, stake):
    """TC_SBP_UI_V3 - the inclusive bounds must be bettable, not merely close.

    EUR 1.00 rests on the unresolved spec conflict recorded in
    docs/02_execution_and_bug_reports.md.
    """
    page.slip.enter_stake(stake)

    assert_payout(stake, page.matches.odds_value("HOME"), page.slip.potential_payout())


@pytest.mark.regression
@pytest.mark.negative
def test_the_stake_field_refuses_non_numeric_input(page):
    """TC_SBP_UI_V4 - a stake with no digits at all must never enable Place Bet.

    Verified live: the real stake input sanitises keystrokes as you type
    rather than rejecting the whole entry - "1.2.3" becomes "1.23", "1.005"
    becomes "1.00", "-10" becomes "10". Each of those lands on a technically
    valid stake, so asserting the button stays disabled for them would be
    asserting something the real UI was never going to do; that case is
    covered as a design choice, not a defect. Only a string that sanitises
    to nothing (no digits) is a meaningful "refuses this input" case here.
    """
    page.slip.enter_stake("abc")

    assert not page.slip.is_place_bet_enabled(), "Place Bet is enabled with a non-numeric stake."


@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.xfail(
    reason="BUG-021: the displayed balance does not refresh after a bet without a "
    "reload, so the client still thinks the old, larger balance covers this stake. "
    "See docs/02.",
    strict=False,
)
def test_a_stake_larger_than_the_balance_is_refused(page):
    """TC_SBP_UI_V5 - insufficient funds, reached by spending down first.

    The ceiling (EUR 100) is below the opening balance (EUR 125.50), so this
    state only exists after a prior bet.
    """
    page.slip.enter_stake("100.00")
    assert page.place_bet_and_wait() == "success", "The setup bet did not go through."
    page.receipt.close()

    page.matches.select_upcoming_odds("HOME")
    page.slip.enter_stake("100.00")

    message = page.slip.validation_message()
    assert (
        "insufficient balance" in message.lower()
    ), f"Expected an insufficient-balance message, the UI shows {message!r}"
    assert not page.slip.is_place_bet_enabled(), "Place Bet is enabled with insufficient funds."


@pytest.mark.regression
@pytest.mark.negative
def test_an_empty_stake_cannot_be_submitted(page):
    """TC_SBP_UI_V6 - the stake is required (specification 4.1)."""
    page.slip.enter_stake("")

    assert not page.slip.is_place_bet_enabled(), "Place Bet is enabled with no stake entered."
