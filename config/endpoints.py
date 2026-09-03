"""Endpoint catalogue, mirroring Feature Specification section 5.3.

Keeping paths in one place means a backend rename is a one-line change and the
feature files can refer to endpoints by a stable, human-readable name.
"""

from __future__ import annotations

from enum import StrEnum


class Endpoint(StrEnum):
    MATCHES = "matches"
    BALANCE = "balance"
    PLACE_BET = "place-bet"
    RESET_BALANCE = "reset-balance"


#: Feature-file name -> (endpoint, JSON schema file) used by the schema assertion step.
SCHEMA_BY_NAME: dict[str, str] = {
    "matches": "matches.schema.json",
    "balance": "balance.schema.json",
    "place_bet": "place_bet.schema.json",
    "reset_balance": "reset_balance.schema.json",
    "error": "error.schema.json",
}
