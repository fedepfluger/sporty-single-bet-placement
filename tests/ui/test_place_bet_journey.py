"""The end-to-end bet placement journey in the browser.

This is the revenue path. If it breaks, the product has no purpose, which is why
the full journey is the one UI flow that runs on every commit.
"""

from __future__ import annotations

import pytest

from tests.support.assertions import assert_payout, to_money

pytestmark = pytest.mark.ui


@pytest.mark.smoke
@pytest.mark.e2e
@pytest.mark.xfail(
    reason="BUG-020: receipt omits Selection and reverses home/away; BUG-021: "
    "header balance does not refresh after a bet without a reload. See docs/02.",
    strict=False,
)
def test_place_a_bet_end_to_end_and_receive_a_consistent_receipt(betting_page, api):
    """TC_SBP_UI_001 - the highest-information test in the suite.

    It transits every component at once - catalogue, slip, API, balance, receipt -
    and asserts the property most likely to be silently wrong: that the numbers
    shown before submission are the numbers on the receipt and in the backend
    afterwards.
    """
    balance_before = api.read_balance()
    assert betting_page.slip.is_empty(), "The bet slip already held a selection before the test started."

    betting_page.matches.select_upcoming_odds("HOME")
    assert (
        "home" in betting_page.slip.market().lower()
    ), f"Selected HOME but the slip shows: {betting_page.slip.market()!r}"
    betting_page.slip.enter_stake("10.00")
    assert_payout("10.00", betting_page.matches.odds_value("HOME"), betting_page.slip.potential_payout())

    assert (
        betting_page.place_bet_and_wait() == "success"
    ), f"Bet placement failed. The error modal said: {betting_page.error_modal.title()!r}"

    receipt = betting_page.receipt.read()
    assert not receipt.missing_fields(), f"The receipt is missing required field(s): {receipt.missing_fields()}"
    assert to_money(receipt.stake) == to_money("10.00")
    assert_payout(receipt.stake, receipt.odds, receipt.payout)

    betting_page.receipt.close()

    assert betting_page.slip.is_empty(), "An active selection survived the receipt being closed."
    assert betting_page.header_balance() == balance_before - to_money("10.00")
    assert betting_page.header_balance() == api.read_balance(), "The UI and the backend disagree on the balance."


@pytest.mark.regression
@pytest.mark.e2e
@pytest.mark.xfail(
    reason="BUG-023: the bet slip drops its balance readout once a selection is active, see docs/02",
    strict=False,
)
def test_the_header_and_the_bet_slip_always_show_the_same_balance(betting_page):
    """TC_SBP_UI_002 - the spec states the balance is shared between the two."""
    betting_page.matches.select_upcoming_odds("DRAW")
    betting_page.slip.enter_stake("5.00")
    assert betting_page.header_balance() == betting_page.slip.balance()

    assert betting_page.place_bet_and_wait() == "success"
    betting_page.receipt.close()

    assert betting_page.header_balance() == betting_page.slip.balance()


@pytest.mark.regression
def test_selecting_a_new_outcome_replaces_the_previous_one(betting_page):
    """TC_SBP_UI_003 - specification 2.2 permits one active selection at a time.

    If a second selection is added rather than substituted, the punter can be
    shown one bet and charged for another.
    """
    index = betting_page.matches.first_upcoming_index()
    betting_page.matches.select_odds("HOME", index=index)
    betting_page.matches.select_odds("AWAY", index=index)

    active = betting_page.matches.active_odds_buttons()
    assert len(active) == 1, f"Expected exactly one active odds button, the page highlights {len(active)}"


@pytest.mark.regression
def test_selecting_an_outcome_on_another_match_replaces_the_slip(betting_page):
    """TC_SBP_UI_004 - the same rule across matches, not only within one."""
    betting_page.matches.select_odds("HOME", index=0)
    betting_page.matches.select_odds("HOME", index=1)

    active = betting_page.matches.active_odds_buttons()
    assert len(active) == 1, f"Expected exactly one active odds button, the page highlights {len(active)}"


@pytest.mark.regression
def test_removing_all_selections_empties_the_slip(betting_page):
    """TC_SBP_UI_005 - Remove All must clear the stake as well as the selection."""
    betting_page.matches.select_upcoming_odds("HOME")
    betting_page.slip.enter_stake("10.00")
    betting_page.slip.remove_all()

    assert betting_page.slip.is_empty(), f"The bet slip still shows: {betting_page.slip.state()}"


@pytest.mark.regression
def test_every_match_card_shows_what_the_spec_requires(betting_page):
    """TC_SBP_UI_007 - specification 2.1: every card carries both teams, a
    kickoff label and the three odds buttons. A card missing one of them is
    unbettable even though the page looks fine."""
    total = betting_page.matches.count()
    assert total > 0, "The match list rendered no matches."

    for index in range(total):
        title = betting_page.matches.title(index)
        assert " vs " in title, f"Match #{index} does not render both teams: {title!r}"
        assert betting_page.matches.kickoff(index), f"Match #{index} renders no kickoff label"
        for selection in ("HOME", "DRAW", "AWAY"):
            assert (
                betting_page.matches.odds_value(selection, index) > 0
            ), f"Match #{index} has no usable {selection} odds"


@pytest.mark.regression
def test_removing_the_selection_empties_the_slip(betting_page):
    """TC_SBP_UI_008 - specification 2.2 lists a per-selection remove (x) as a
    control of its own, next to Remove All. Both must clear the slip."""
    betting_page.matches.select_upcoming_odds("HOME")
    betting_page.slip.enter_stake("10.00")
    betting_page.slip.remove_selection()

    assert betting_page.slip.is_empty(), f"The bet slip still shows: {betting_page.slip.state()}"


@pytest.mark.smoke
def test_the_match_list_renders_without_client_side_errors(betting_page):
    """TC_SBP_UI_006 - the cheapest possible check that the page is not broken."""
    assert betting_page.matches.count() > 0, "The match list rendered no matches."

    errors = betting_page.browser_errors()
    assert not errors, "The browser reported severe console errors:\n" + "\n".join(errors)
