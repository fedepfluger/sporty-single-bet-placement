"""Reusable assertion helpers shared by the API and UI layers."""

from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from config.endpoints import SCHEMA_BY_NAME
from config.settings import SCHEMAS_DIR

_MONEY_PATTERN = re.compile(r"-?\d[\d.,]*")


def load_schema(name: str) -> dict[str, Any]:
    try:
        filename = SCHEMA_BY_NAME[name]
    except KeyError as exc:
        raise AssertionError(f"Unknown schema '{name}'. Known: {sorted(SCHEMA_BY_NAME)}") from exc
    return json.loads((Path(SCHEMAS_DIR) / filename).read_text(encoding="utf-8"))


def assert_matches_schema(payload: Any, schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        details = "\n".join(f"  - {'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors)
        raise AssertionError(f"Response does not match the '{schema_name}' schema:\n{details}")


def to_money(value: Any) -> Decimal:
    """Parse a number, a '12.34' string or a '€12.34' UI label into a Decimal."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    match = _MONEY_PATTERN.search(str(value))
    if not match:
        raise AssertionError(f"Cannot read a monetary amount from {value!r}")
    return Decimal(match.group().replace(",", ""))


def round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def assert_payout(stake: Any, odds: Any, payout: Any) -> None:
    """Payout must equal stake x odds, rounded to cents (Domain Context, 'Payout')."""
    expected = round_money(to_money(stake) * to_money(odds))
    actual = round_money(to_money(payout))
    assert (
        actual == expected
    ), f"Payout mismatch: stake {stake} x odds {odds} should be {expected}, API returned {actual}"


def assert_decimal_places(value: Any, maximum: int) -> None:
    exponent = -to_money(value).as_tuple().exponent
    assert exponent <= maximum, f"{value} has {exponent} decimal places, the maximum allowed is {maximum}"
