"""POST /api/reset-balance - restores a known starting balance.

This endpoint is the suite's own test-data lever. If it lies about the state it
wrote, every balance assertion in the project becomes unreliable, so its
response/state consistency is asserted explicitly rather than assumed.
"""

from __future__ import annotations

import pytest

from config.endpoints import Endpoint
from tests.app_actions.api.http_client import OMIT
from tests.support import payloads
from tests.support.api_assertions import assert_schema, assert_status
from tests.support.assertions import to_money

pytestmark = pytest.mark.api


# --- Happy path --------------------------------------------------------------
@pytest.mark.smoke
def test_reset_restores_the_initial_balance(api, settings):
    """TC_SBP_RESET_001 - the documented starting balance is restored."""
    response = api.reset_balance()

    assert_status(response, 200)
    payload = assert_schema(response, "reset_balance")
    assert to_money(payload["balance"]) == settings.rules.initial_balance
    assert payload["currency"] == "EUR"


@pytest.mark.smoke
@pytest.mark.xfail(reason="BUG-012: reset-balance reports a balance it does not persist, see docs/02", strict=False)
def test_the_reset_response_and_the_persisted_state_agree(api, match, settings):
    """TC_SBP_RESET_002 - specification 5.3 requires the body and the stored
    state to be consistent after a reset. Spend first, so the reset has work to do."""
    assert_status(api.place_bet(match_id=match["id"], selection="HOME", stake=10.00), 200)

    response = api.reset_balance()

    assert_status(response, 200)
    responded = to_money(response.json()["balance"])
    assert responded == settings.rules.initial_balance
    assert (
        api.read_balance() == responded
    ), f"The reset response reported {responded} but GET /api/balance reports {api.read_balance()}"


@pytest.mark.regression
@pytest.mark.xfail(reason="BUG-012: reset-balance reports a balance it does not persist, see docs/02", strict=False)
def test_resetting_twice_is_idempotent(api, settings):
    """TC_SBP_RESET_003 - a repeated reset must not compound or drift."""
    assert_status(api.reset_balance(), 200)
    response = api.reset_balance()

    assert_status(response, 200)
    responded = to_money(response.json()["balance"])
    assert responded == settings.rules.initial_balance
    assert api.read_balance() == responded


# --- Authentication ----------------------------------------------------------
@pytest.mark.smoke
@pytest.mark.security
def test_absent_user_context_is_rejected(api):
    """TC_SBP_RESET_A1 - an anonymous caller must not be able to mint funds."""
    response = api.client.with_user_id(OMIT).post(Endpoint.RESET_BALANCE, json_body={})

    assert_status(response, 401)


@pytest.mark.regression
@pytest.mark.security
def test_empty_user_context_is_rejected(api):
    """TC_SBP_RESET_A2 - the header is present but carries no identity."""
    response = api.client.with_user_id("").post(Endpoint.RESET_BALANCE, json_body={})

    assert_status(response, 401)


# --- Protocol ----------------------------------------------------------------
@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_unsupported_http_method_is_rejected(api, method):
    """TC_SBP_RESET_P1 - a state-changing endpoint must not answer a GET."""
    response = api.call_with_method(Endpoint.RESET_BALANCE, method)

    assert_status(response, 405)


@pytest.mark.regression
@pytest.mark.parametrize("value", payloads.HOSTILE_HEADER_VALUES.values(), ids=payloads.HOSTILE_HEADER_VALUES)
def test_unknown_request_header_is_ignored(api, value):
    """TC_SBP_RESET_H1 - an unrecognized header must not alter the outcome."""
    response = api.client.with_headers({"extra": value}).post(Endpoint.RESET_BALANCE, json_body={})

    assert_status(response, 200)
