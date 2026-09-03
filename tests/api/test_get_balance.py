"""GET /api/balance - the punter's available funds.

Balance is the money-critical read: the header, the bet slip and the stake
validation all trust it, so a wrong value is a direct financial risk.
"""

from __future__ import annotations

import pytest

from config.endpoints import Endpoint
from tests.app_actions.api.http_client import OMIT
from tests.support import payloads
from tests.support.api_assertions import assert_money_precision, assert_no_server_error, assert_schema, assert_status
from tests.support.assertions import to_money

pytestmark = pytest.mark.api


# --- Happy path --------------------------------------------------------------
@pytest.mark.smoke
def test_balance_is_returned_in_euros(api):
    """TC_SBP_BALANCE_001 - the balance is served and matches its contract."""
    response = api.get_balance()

    assert_status(response, 200)
    payload = assert_schema(response, "balance")
    assert payload["currency"] == "EUR", f"Expected EUR, the API returned {payload['currency']!r}"


@pytest.mark.regression
@pytest.mark.xfail(reason="BUG-012: reset-balance reports a balance it does not persist, see docs/02", strict=False)
def test_a_freshly_reset_balance_reports_the_initial_amount(clean_balance, api, settings):
    """TC_SBP_BALANCE_002 - the documented starting balance of the spec."""
    response = api.get_balance()

    assert_status(response, 200)
    assert to_money(response.json()["balance"]) == settings.rules.initial_balance


@pytest.mark.regression
def test_monetary_values_carry_at_most_two_decimals(api):
    """TC_SBP_BALANCE_003 - business rule 3: stake precision is two decimals,
    so a balance with more is either a rounding bug or a display hazard."""
    response = api.get_balance()

    assert_status(response, 200)
    assert_money_precision(response.json())


# --- Unknown query parameters ------------------------------------------------
@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("value", payloads.HOSTILE_QUERY_VALUES.values(), ids=payloads.HOSTILE_QUERY_VALUES)
def test_hostile_query_parameter_does_not_corrupt_the_balance_read(api, value):
    """TC_SBP_BALANCE_E1 - a junk parameter must not change what is returned."""
    response = api.get_balance(params={"extra": value})

    assert_no_server_error(response)
    assert_schema(response, "balance")


# --- Unknown headers ---------------------------------------------------------
@pytest.mark.regression
@pytest.mark.parametrize("value", payloads.HOSTILE_HEADER_VALUES.values(), ids=payloads.HOSTILE_HEADER_VALUES)
def test_unknown_request_header_is_ignored(api, value):
    """TC_SBP_BALANCE_H1 - an unrecognized header must not alter the response."""
    response = api.client.with_headers({"extra": value}).get(Endpoint.BALANCE)

    assert_status(response, 200)
    assert_schema(response, "balance")


# --- Authentication ----------------------------------------------------------
@pytest.mark.smoke
@pytest.mark.security
def test_absent_user_context_is_rejected(api):
    """TC_SBP_BALANCE_A1 - a balance must never be served without an identity."""
    response = api.client.with_user_id(OMIT).get(Endpoint.BALANCE)

    assert_status(response, 401)
    # The spec leaves the error body undefined; `error.schema.json` records the
    # minimum we are willing to assume (see docs/02, BUG-002).
    assert_schema(response, "error")


@pytest.mark.regression
@pytest.mark.security
def test_empty_user_context_is_rejected(api):
    """TC_SBP_BALANCE_A2 - the header is present but carries no identity."""
    response = api.client.with_user_id("").get(Endpoint.BALANCE)

    assert_status(response, 401)


@pytest.mark.regression
@pytest.mark.security
@pytest.mark.spec_gap
def test_an_unknown_user_id_never_sees_another_punters_funds(api, settings):
    """TC_SBP_BALANCE_A3 - the spec does not say whether an unprovisioned but
    well-formed id is rejected or silently created, so we assert the property
    that matters either way: it must not inherit somebody else's money."""
    response = api.client.with_user_id(settings.unknown_user_id).get(Endpoint.BALANCE)

    if response.status_code in (401, 403, 404):
        return

    assert_status(response, 200)
    balance = to_money(response.json()["balance"])
    assert balance == settings.rules.initial_balance, (
        f"An unprovisioned user id was served a balance of {balance} instead of a clean "
        f"{settings.rules.initial_balance}. This would mean user data leaks across identities."
    )


# --- Protocol ----------------------------------------------------------------
@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_unsupported_http_method_is_rejected(api, method):
    """TC_SBP_BALANCE_P1 - the balance is read-only."""
    response = api.call_with_method(Endpoint.BALANCE, method)

    assert_status(response, 405)
