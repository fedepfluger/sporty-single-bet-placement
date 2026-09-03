"""POST /api/place-bet - every stake, selection and protocol rule.

This is the only endpoint that moves money. Every rule in sections 3 and 4 of the
specification is asserted here, at the layer where the rule actually lives: the
API must reject an invalid bet even when the UI would have blocked it.

Each test that can spend money takes `clean_balance`, which resets the punter to
a known starting balance before and after it runs.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from config.endpoints import Endpoint
from tests.app_actions.api.betting_api_actions import BettingApiActions
from tests.app_actions.api.http_client import OMIT
from tests.support import payloads
from tests.support.api_assertions import (
    assert_balance_decreased_by_stake,
    assert_balance_unchanged,
    assert_error_mentions,
    assert_money_precision,
    assert_no_server_error,
    assert_schema,
    assert_status,
)
from tests.support.assertions import assert_payout, to_money
from tests.support.payloads import bet_body

pytestmark = pytest.mark.api


# --- Happy path --------------------------------------------------------------
@pytest.mark.smoke
@pytest.mark.xfail(reason="BUG-013: place-bet returns currency USD instead of EUR, see docs/02", strict=False)
def test_place_a_valid_single_bet(clean_balance, api, match, balance_before):
    """TC_SBP_BET_001 - the revenue path: the bet is accepted, priced correctly
    and debited exactly once."""
    response = api.place_bet(match_id=match["id"], selection="HOME", stake=10.00)

    assert_status(response, 200)
    payload = assert_schema(response, "place_bet")
    assert payload["matchId"] == match["id"]
    assert payload["selection"] == "HOME"
    assert_payout(payload["stake"], payload["odds"], payload["payout"])
    assert_balance_decreased_by_stake(payload, balance_before)


@pytest.mark.smoke
@pytest.mark.parametrize("selection", ["HOME", "DRAW", "AWAY"])
def test_every_documented_selection_can_be_backed(clean_balance, api, match, selection):
    """TC_SBP_BET_002 - all three markets are bettable and priced from the catalogue."""
    response = api.place_bet(match_id=match["id"], selection=selection, stake=1.00)

    assert_status(response, 200)
    payload = response.json()
    assert payload["matchId"] == match["id"]
    assert payload["selection"] == selection
    assert to_money(payload["odds"]) == api.odds_for(match, selection), (
        f"Bet was priced at {payload['odds']} but the catalogue advertises "
        f"{api.odds_for(match, selection)} for {selection}"
    )


@pytest.mark.regression
def test_odds_are_static_and_the_bet_is_not_repriced(clean_balance, api, match):
    """TC_SBP_BET_003 - business rule 3 says odds are static for the session, so
    the price at placement must equal the price advertised."""
    response = api.place_bet(match_id=match["id"], selection="HOME", stake=5.00)

    assert_status(response, 200)
    payload = response.json()
    assert to_money(payload["odds"]) == api.odds_for(match, "HOME")
    assert_money_precision(payload)


@pytest.mark.regression
@pytest.mark.security
def test_client_supplied_payout_and_balance_are_never_trusted(clean_balance, api, match, balance_before):
    """TC_SBP_BET_004 - a client that sends its own payout, balance and odds must
    not be able to talk the backend into honoring them."""
    response = api.place_bet(
        match_id=match["id"],
        selection="HOME",
        stake=1.00,
        extra_fields={"payout": 999999, "balance": 999999, "isAdmin": True, "odds": 1000},
    )

    assert_status(response, 200)
    payload = response.json()
    assert_payout(payload["stake"], payload["odds"], payload["payout"])
    assert_balance_decreased_by_stake(payload, balance_before)


# --- Stake boundaries --------------------------------------------------------
@pytest.mark.smoke
@pytest.mark.boundary
@pytest.mark.spec_gap
def test_the_minimum_stake_is_accepted(clean_balance, api, match):
    """TC_SBP_BET_B1 - spec conflict (BUG-001): business rules and UI copy say
    EUR 1.00, section 4.1 says EUR 1.01. We assert the documented minimum of
    EUR 1.00. See docs/02_execution_and_bug_reports.md."""
    response = api.place_bet(match_id=match["id"], selection="HOME", stake=1.00)

    assert_status(response, 200)


@pytest.mark.smoke
@pytest.mark.boundary
def test_the_maximum_stake_is_accepted(clean_balance, api, match, balance_before):
    """TC_SBP_BET_B3 - EUR 100.00 is the documented ceiling and must be bettable."""
    response = api.place_bet(match_id=match["id"], selection="HOME", stake=100.00)

    assert_status(response, 200)
    assert_balance_decreased_by_stake(response.json(), balance_before)


#: BUG-014: 0, 0.01 and 0.99 are correctly rejected; negative stakes are not -
#: the API accepts them and returns a negative payout. See docs/02.
_STAKES_BELOW_MINIMUM_PARAMS = [
    (
        pytest.param(
            stake,
            marks=pytest.mark.xfail(reason="BUG-014: negative stakes are accepted, see docs/02", strict=False),
        )
        if stake.startswith("-")
        else stake
    )
    for stake in payloads.STAKES_BELOW_MINIMUM
]


@pytest.mark.regression
@pytest.mark.boundary
@pytest.mark.negative
@pytest.mark.parametrize("stake", _STAKES_BELOW_MINIMUM_PARAMS)
def test_stakes_below_the_minimum_are_rejected(clean_balance, api, match, balance_before, stake):
    """TC_SBP_BET_B2 - below EUR 1.00, including zero and negatives."""
    response = api.place_bet_with_body(bet_body(match["id"], "HOME", float(stake)))

    assert_status(response, 422)
    assert_balance_unchanged(api, balance_before)


@pytest.mark.regression
@pytest.mark.boundary
@pytest.mark.negative
@pytest.mark.parametrize("stake", payloads.STAKES_ABOVE_MAXIMUM)
def test_stakes_above_the_maximum_are_rejected(clean_balance, api, match, balance_before, stake):
    """TC_SBP_BET_B4 - above EUR 100.00, including a stake the punter could afford."""
    response = api.place_bet_with_body(bet_body(match["id"], "HOME", float(stake)))

    assert_status(response, 422)
    assert_balance_unchanged(api, balance_before)


@pytest.mark.regression
@pytest.mark.boundary
@pytest.mark.negative
@pytest.mark.parametrize("stake", payloads.STAKES_WITH_EXCESS_PRECISION)
def test_stakes_with_more_than_two_decimals_are_rejected(clean_balance, api, match, balance_before, stake):
    """TC_SBP_BET_B5 - accepting a third decimal means the debit and the receipt
    can disagree by a rounding step."""
    response = api.place_bet_with_body(bet_body(match["id"], "HOME", float(stake)))

    assert_status(response, 422)
    assert_balance_unchanged(api, balance_before)


@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("stake", payloads.NON_NUMERIC_STAKES.values(), ids=payloads.NON_NUMERIC_STAKES)
def test_non_numeric_stakes_are_rejected(clean_balance, api, match, balance_before, stake):
    """TC_SBP_BET_B6 - anything the API cannot price, including JSON null and
    injection-shaped strings."""
    response = api.place_bet_with_body(bet_body(match["id"], "HOME", stake))

    assert_status(response, 400, 422)
    assert_no_server_error(response)
    assert_balance_unchanged(api, balance_before)


@pytest.mark.regression
@pytest.mark.negative
def test_a_missing_stake_is_rejected(clean_balance, api, match, balance_before):
    """TC_SBP_BET_B7 - the field is absent entirely, not merely empty."""
    response = api.place_bet_with_body(bet_body(match_id=match["id"], selection="HOME"))

    assert_status(response, 422)
    assert_balance_unchanged(api, balance_before)


@pytest.mark.regression
@pytest.mark.boundary
@pytest.mark.xfail(
    reason="BUG-015: a stake above the balance is accepted and drives it negative, see docs/02", strict=False
)
def test_a_stake_above_the_remaining_balance_is_refused(clean_balance, api, match):
    """TC_SBP_BET_B8 - insufficient funds.

    The stake ceiling (EUR 100) sits below the opening balance (EUR 125.50), so
    this state is only reachable after prior spend - exactly the kind of path an
    untested rule hides in.
    """
    setup = api.place_bet(match_id=match["id"], selection="HOME", stake=100.00)
    assert_status(setup, 200)
    balance_after_setup = api.read_balance()

    response = api.place_bet(match_id=match["id"], selection="HOME", stake=50.00)

    assert_status(response, 422)
    assert_schema(response, "error")
    assert_error_mentions(response, "balance")
    assert_balance_unchanged(api, balance_after_setup)


# --- Selection validation ----------------------------------------------------
@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("selection", payloads.INVALID_SELECTIONS.values(), ids=payloads.INVALID_SELECTIONS)
def test_invalid_selections_are_rejected(clean_balance, api, match, balance_before, selection):
    """TC_SBP_BET_S1 - only HOME, DRAW and AWAY exist; case variants are not aliases."""
    response = api.place_bet_with_body(bet_body(match["id"], selection, 1.00))

    assert_status(response, 400, 422)
    assert_balance_unchanged(api, balance_before)


@pytest.mark.regression
@pytest.mark.negative
def test_a_missing_selection_is_rejected(clean_balance, api, match, balance_before):
    """TC_SBP_BET_S2 - a bet without an outcome cannot be settled."""
    response = api.place_bet_with_body(bet_body(match_id=match["id"], stake=1.00))

    assert_status(response, 422)
    assert_balance_unchanged(api, balance_before)


# --- Match validation --------------------------------------------------------
@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("match_id", payloads.INVALID_MATCH_IDS.values(), ids=payloads.INVALID_MATCH_IDS)
def test_unknown_or_malformed_match_ids_are_rejected(clean_balance, api, balance_before, match_id):
    """TC_SBP_BET_M1 - a bet on a fixture that does not exist has no settlement path."""
    response = api.place_bet_with_body(bet_body(match_id, "HOME", 1.00))

    assert_status(response, 400, 422)
    assert_no_server_error(response)
    assert_balance_unchanged(api, balance_before)


@pytest.mark.regression
@pytest.mark.negative
def test_a_missing_match_id_is_rejected(clean_balance, api, balance_before):
    """TC_SBP_BET_M2 - the field is absent entirely."""
    response = api.place_bet_with_body(bet_body(selection="HOME", stake=1.00))

    assert_status(response, 422)
    assert_balance_unchanged(api, balance_before)


# --- Protocol validation -----------------------------------------------------
#: BUG-016: `plain_text` and `truncated_json` crash the server with HTTP 500
#: instead of being rejected with 400. The rest are correctly rejected. See docs/02.
_MALFORMED_BODY_XFAIL_IDS = {"plain_text", "truncated_json"}
_MALFORMED_BODY_PARAMS = [
    pytest.param(
        value,
        id=key,
        marks=(
            pytest.mark.xfail(
                reason="BUG-016: a malformed body crashes the server with HTTP 500, see docs/02", strict=False
            )
            if key in _MALFORMED_BODY_XFAIL_IDS
            else ()
        ),
    )
    for key, value in payloads.MALFORMED_RAW_BODIES.items()
]


@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("raw", _MALFORMED_BODY_PARAMS)
def test_malformed_payloads_are_rejected(api, raw):
    """TC_SBP_BET_P1 - specification 4.3: non-object payloads are bad requests.
    Note `12345`, `true` and `null` are valid JSON but are not objects."""
    response = api.place_bet_with_raw_body(raw)

    assert_status(response, 400)
    assert_no_server_error(response)


@pytest.mark.regression
@pytest.mark.negative
def test_a_json_array_is_not_a_valid_request_object(api):
    """TC_SBP_BET_P2 - an array would let a client smuggle in a multi-bet."""
    response = api.place_bet_with_body([{"matchId": "x", "selection": "HOME", "stake": 1}])

    assert_status(response, 400, 422)


@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.xfail(reason="BUG-017: an empty body returns 422 instead of the documented 400, see docs/02", strict=False)
def test_an_empty_body_is_rejected(api):
    """TC_SBP_BET_P3 - no payload at all."""
    response = api.place_bet_with_raw_body("")

    assert_status(response, 400)


@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize(
    "method",
    [
        pytest.param(
            "GET",
            marks=pytest.mark.xfail(
                reason="BUG-018: GET is accepted on place-bet instead of 405, see docs/02", strict=False
            ),
        ),
        "PUT",
        "PATCH",
        "DELETE",
    ],
)
def test_unsupported_http_method_is_rejected(api, method):
    """TC_SBP_BET_P4 - placement is POST-only."""
    response = api.call_with_method(Endpoint.PLACE_BET, method)

    assert_status(response, 405)


# --- Authentication ----------------------------------------------------------
@pytest.mark.smoke
@pytest.mark.security
def test_a_bet_without_a_user_context_is_rejected(api, match):
    """TC_SBP_BET_A1 - rejected before any money moves."""
    response = api.client.with_user_id(OMIT).post(Endpoint.PLACE_BET, json_body=bet_body(match["id"], "HOME", 1.00))

    assert_status(response, 401)


@pytest.mark.regression
@pytest.mark.security
def test_a_bet_with_an_empty_user_context_is_rejected(api, match):
    """TC_SBP_BET_A2 - the header is present but carries no identity."""
    response = api.client.with_user_id("").post(Endpoint.PLACE_BET, json_body=bet_body(match["id"], "HOME", 1.00))

    assert_status(response, 401)


# --- Concurrency -------------------------------------------------------------
@pytest.mark.regression
@pytest.mark.concurrency
@pytest.mark.slow
@pytest.mark.xfail(
    reason="BUG-019: no 409 protection exists, two simultaneous bets both succeed, see docs/02", strict=False
)
def test_two_simultaneous_bets_cannot_both_be_accepted(clean_balance, api, match):
    """TC_SBP_BET_C1 - section 5.3 documents a 409 for 'bet already in progress'.

    If both requests succeed the punter can spend the same balance twice, so the
    assertion is on the invariant rather than on the exact status pairing.
    """

    def place():
        # A dedicated client per thread: `requests.Session` is not thread-safe.
        return BettingApiActions().place_bet(match["id"], "HOME", 1.00)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result() for future in [pool.submit(place), pool.submit(place)]]

    statuses = [response.status_code for response in responses]
    accepted = statuses.count(200)
    assert accepted <= 1, f"The API accepted {accepted} simultaneous bets for the same user; statuses were {statuses}"
