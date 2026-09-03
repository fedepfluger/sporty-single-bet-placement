"""GET /api/matches - the upcoming football catalogue.

The match list is the entry point of the whole betting flow: if it is wrong,
every downstream bet is priced against wrong data.
"""

from __future__ import annotations

from datetime import date

import pytest

from config.endpoints import Endpoint
from tests.app_actions.api.http_client import OMIT
from tests.support import payloads
from tests.support.api_assertions import assert_no_server_error, assert_schema, assert_status
from tests.support.assertions import to_money

pytestmark = pytest.mark.api


# --- Happy path --------------------------------------------------------------
@pytest.mark.smoke
def test_catalogue_returns_upcoming_matches(api):
    """TC_SBP_MATCHES_001 - the catalogue is served and matches its contract."""
    response = api.get_matches()

    assert_status(response, 200)
    matches = assert_schema(response, "matches")
    assert len(matches) >= 1, "The catalogue is empty; no bet could be placed."


@pytest.mark.regression
@pytest.mark.xfail(
    reason="BUG-011: the catalogue serves 74 past fixtures before any upcoming one, see docs/02", strict=False
)
def test_catalogue_respects_the_documented_business_rules(api, settings):
    """TC_SBP_MATCHES_002 - unique ids, odds in range, pre-match fixtures only."""
    matches = api.list_matches()
    rules = settings.rules

    ids = [match["id"] for match in matches]
    assert len(ids) == len(set(ids)), f"The catalogue returns duplicated match ids: {sorted(ids)}"

    for match in matches:
        for market, value in match["odds"].items():
            odds = to_money(value)
            assert rules.odds_min <= odds <= rules.odds_max, (
                f"Match {match['id']} exposes {market} odds of {odds}, "
                f"outside the allowed {rules.odds_min}-{rules.odds_max} range"
            )

    today = date.today().isoformat()
    past = [match["id"] for match in matches if match["kickoffDate"][:10] < today]
    assert not past, f"The catalogue offers matches that have already kicked off: {past}"


# --- Unknown query parameters ------------------------------------------------
@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.spec_gap
def test_unknown_query_parameter_does_not_break_the_catalogue(api):
    """TC_SBP_MATCHES_E1 - the spec is silent, so we assert the safe reading:
    an unrecognized parameter is ignored rather than fatal."""
    response = api.get_matches(params={"extra": "extra_parameter"})

    assert_no_server_error(response)
    assert_status(response, 200)


@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("value", payloads.HOSTILE_QUERY_VALUES.values(), ids=payloads.HOSTILE_QUERY_VALUES)
def test_hostile_query_parameter_does_not_reach_the_backend(api, value):
    """TC_SBP_MATCHES_E2 - injection-shaped parameters must not crash the service."""
    response = api.get_matches(params={"extra": value})

    assert_no_server_error(response)


@pytest.mark.regression
@pytest.mark.negative
def test_extra_path_segment_does_not_resolve(api):
    """TC_SBP_MATCHES_E3 - a fabricated sub-resource must not be served."""
    response = api.client.get(f"{Endpoint.MATCHES}/admin.html")

    assert_status(response, 404, 405)


# --- Unknown headers ---------------------------------------------------------
@pytest.mark.regression
@pytest.mark.parametrize("value", payloads.HOSTILE_HEADER_VALUES.values(), ids=payloads.HOSTILE_HEADER_VALUES)
def test_unknown_request_header_is_ignored(api, value):
    """TC_SBP_MATCHES_H1 - an unrecognized header must not alter the response."""
    response = api.client.with_headers({"extra": value}).get(Endpoint.MATCHES)

    assert_status(response, 200)
    assert_schema(response, "matches")


# --- Authentication ----------------------------------------------------------
@pytest.mark.smoke
@pytest.mark.security
def test_absent_user_context_is_rejected(api):
    """TC_SBP_MATCHES_A1 - no x-user-id header at all."""
    response = api.client.with_user_id(OMIT).get(Endpoint.MATCHES)

    assert_status(response, 401)


@pytest.mark.regression
@pytest.mark.security
@pytest.mark.parametrize("user_id", ["", "null"], ids=["empty", "null_literal"])
def test_malformed_user_context_is_rejected(api, user_id):
    """TC_SBP_MATCHES_A2 / A3 - the header is present but carries no identity."""
    response = api.client.with_user_id(user_id).get(Endpoint.MATCHES)

    assert_status(response, 401)


# --- Protocol ----------------------------------------------------------------
@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_unsupported_http_method_is_rejected(api, method):
    """TC_SBP_MATCHES_P1 - specification 4.3 requires a method-not-allowed response."""
    response = api.call_with_method(Endpoint.MATCHES, method)

    assert_status(response, 405)
