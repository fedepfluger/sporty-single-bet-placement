"""Response-level assertions shared across the API tests.

These exist for the checks whose failure message is worth writing once: status
codes (which must show the body, or the failure is undiagnosable), schema
conformance, and the "no money moved" property. Everything simpler stays as a
plain `assert` in the test, where it reads better than a helper call.
"""

from __future__ import annotations

from decimal import Decimal

import requests

from tests.app_actions.api.betting_api_actions import BettingApiActions
from tests.support.assertions import assert_decimal_places, assert_matches_schema, to_money

MONETARY_FIELDS = ("stake", "payout", "balance")


def body_of(response: requests.Response) -> object:
    """Parse a JSON body, failing with the raw payload instead of a decode error."""
    try:
        return response.json()
    except ValueError as exc:
        raise AssertionError(
            f"Expected a JSON body but got content-type "
            f"'{response.headers.get('Content-Type')}': {response.text[:300]!r}"
        ) from exc


def assert_status(response: requests.Response, *allowed: int) -> None:
    """Assert the status code, always quoting the body so a failure is actionable."""
    if response.status_code in allowed:
        return
    expected = str(allowed[0]) if len(allowed) == 1 else f"one of {list(allowed)}"
    raise AssertionError(f"Expected HTTP {expected} but got HTTP {response.status_code}. Body: {response.text[:500]}")


def assert_no_server_error(response: requests.Response) -> None:
    """Invalid input must produce a 4xx. A 5xx means the input crashed the backend."""
    assert response.status_code < 500, (
        f"The API answered HTTP {response.status_code}; invalid input must never cause a server error. "
        f"Body: {response.text[:500]}"
    )


def assert_schema(response: requests.Response, schema_name: str) -> object:
    """Validate the body against a contract in `config/schemas/` and return it."""
    payload = body_of(response)
    assert_matches_schema(payload, schema_name)
    return payload


def assert_error_mentions(response: requests.Response, fragment: str) -> None:
    assert (
        fragment.lower() in response.text.lower()
    ), f"Expected the error body to mention '{fragment}'. Body: {response.text[:400]}"


def assert_money_precision(payload: dict) -> None:
    for field in MONETARY_FIELDS:
        if field in payload:
            assert_decimal_places(payload[field], 2)


def assert_balance_unchanged(api: BettingApiActions, expected: Decimal) -> None:
    """A rejected request must never move money."""
    current = api.read_balance()
    assert current == expected, f"A rejected request changed the balance from {expected} to {current}"


def assert_balance_decreased_by_stake(payload: dict, balance_before: Decimal) -> None:
    expected = balance_before - to_money(payload["stake"])
    actual = to_money(payload["balance"])
    assert actual == expected, (
        f"Balance should have gone from {balance_before} to {expected} "
        f"after a stake of {payload['stake']}, but the API returned {actual}"
    )
