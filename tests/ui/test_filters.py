"""Match filters narrow the catalogue and reject impossible ranges.

Filters are lower risk than placement, so they sit in regression only. The
inverted-range case is kept because silently returning nothing hides a bug:
an empty list reads as "no fixtures today" rather than "your filter is impossible".
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui


@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.xfail(
    reason="BUG-022: an inverted odds range is silently accepted with no feedback and no effect, see docs/02",
    strict=False,
)
def test_an_inverted_odds_range_is_rejected_with_clear_feedback(betting_page):
    """TC_SBP_UI_F1 - specification 2.6 requires clear feedback, not an empty list."""
    betting_page.filters.by_odds("5.00", "1.50")

    message = betting_page.filters.error()
    assert "range" in message.lower(), f"Expected feedback about the invalid range, the UI shows {message!r}"


@pytest.mark.regression
@pytest.mark.boundary
def test_an_odds_range_is_inclusive_of_its_bounds(betting_page):
    """TC_SBP_UI_F2 - the spec states the range is inclusive.

    The filter control's own bounds are 1.00-10.00 (its slider `min`/`max`),
    narrower than the business rule's 1.01-1000.00 odds range - that ceiling
    governs a match's odds value, not this control's input range.
    """
    betting_page.filters.by_odds("1.00", "10.00")

    assert betting_page.matches.count() > 0, "A filter spanning the control's full range returned nothing."
