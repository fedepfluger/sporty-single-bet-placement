"""Test data: hostile inputs, boundary values and request-body construction.

Keeping the datasets here rather than inline in the tests means a new class of
hostile input reaches every negative test at once, and that the values stay
typed - a `None` is a real JSON null, not the string "null", and the difference
between the two is asserted separately.
"""

from __future__ import annotations

from typing import Any

#: Sentinel for "omit this field from the request body entirely", which is a
#: different assertion from sending it as null or as an empty string.
MISSING: Any = object()


# --- Hostile strings ---------------------------------------------------------
# Query strings and HTTP headers can only carry text, so every value here is a
# string. A JSON body can carry a real null, which is covered separately below.

BASH_CODE = "set --f -s -t"
JS_FUNCTION = "(function(){ctx.clearRect(0,0,960,720);ctx.fillStyle='#000000'})"
PSEUDO_LOCALIZED = "λèℓℓô_ƭλïƨ_ïƨ_á_ƭèƨƭ"
#: HTTP header values must be latin-1 encodable (RFC 7230), so headers get an
#: accented-but-encodable variant rather than the full-width one above.
PSEUDO_LOCALIZED_HEADER = "9è¥úïôáJçñ ôè ïú ôô ï áè"
AWK_INSTRUCTION = "BEGIN{ENCODING=-4;}"
SQL_INJECTION = "' OR '1'='1"
XSS = "<script>alert('xss')</script>"
LONG_STRING = "A" * 5000

#: Values an attacker or a broken client might put in a query parameter.
HOSTILE_QUERY_VALUES: dict[str, str] = {
    "null_literal": "null",
    "empty": "",
    "bash_code": BASH_CODE,
    "js_function": JS_FUNCTION,
    "pseudo_localized": PSEUDO_LOCALIZED,
    "awk_instruction": AWK_INSTRUCTION,
    "sql_injection": SQL_INJECTION,
    "xss": XSS,
    "long_string": LONG_STRING,
}

#: Same idea for headers, minus the values HTTP itself cannot transport.
HOSTILE_HEADER_VALUES: dict[str, str] = {
    "plain": "extra_header",
    "null_literal": "null",
    "empty": "",
    "bash_code": BASH_CODE,
    "js_function": JS_FUNCTION,
    "pseudo_localized": PSEUDO_LOCALIZED_HEADER,
    "awk_instruction": AWK_INSTRUCTION,
}


# --- Business-rule boundaries (Feature Specification sections 3 and 4) -------
STAKES_BELOW_MINIMUM = ["0.99", "0.01", "0", "-1", "-50"]
STAKES_ABOVE_MAXIMUM = ["100.01", "125.50", "999999.99"]
STAKES_WITH_EXCESS_PRECISION = ["1.005", "10.999", "2.0000001"]

#: Anything the API cannot price. `None` is a real JSON null, not a string.
NON_NUMERIC_STAKES: dict[str, Any] = {
    "word": "ten",
    "scientific_notation": "1e2",
    "comma_decimal": "1,00",
    "nan": "NaN",
    "infinity": "Infinity",
    "empty": "",
    "null": None,
    "sql_injection": SQL_INJECTION,
    "xss": XSS,
    "bash_code": BASH_CODE,
    "awk_instruction": AWK_INSTRUCTION,
}

#: Selections outside the documented HOME / DRAW / AWAY enum, including the
#: near-misses (case variants) that a careless client is most likely to send.
INVALID_SELECTIONS: dict[str, Any] = {
    "lowercase": "home",
    "title_case": "Home",
    "verbose": "HOME_TEAM",
    "synonym": "WIN",
    "numeric": "1",
    "empty": "",
    "null": None,
    "sql_injection": SQL_INJECTION,
    "xss": XSS,
}

INVALID_MATCH_IDS: dict[str, Any] = {
    "unknown": "does-not-exist",
    "zero_uuid": "00000000-0000-0000-0000-000000000000",
    "empty": "",
    "null": None,
    "sql_injection": SQL_INJECTION,
    "xss": XSS,
    "long_string": LONG_STRING,
}

#: Raw request bodies that are not a valid JSON object. Note that `12345`,
#: `true` and `null` are valid JSON but not objects, which section 5.3 also rejects.
MALFORMED_RAW_BODIES: dict[str, str] = {
    "plain_text": "not-json-at-all",
    "truncated_json": '{"matchId":',
    "json_string": '"just a string"',
    "json_number": "12345",
    "json_boolean": "true",
    "json_null": "null",
}


def bet_body(match_id: Any = MISSING, selection: Any = MISSING, stake: Any = MISSING, **extra: Any) -> dict[str, Any]:
    """Build a place-bet body, omitting any field left as `MISSING`.

    This is what makes "the field is absent" and "the field is null" two
    distinct, separately asserted cases.
    """
    body = {"matchId": match_id, "selection": selection, "stake": stake, **extra}
    return {key: value for key, value in body.items() if value is not MISSING}
