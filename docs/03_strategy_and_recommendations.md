# Strategy & Recommendations

## 1. Why these tests were automated

The assignment asks for two high-value automated tests. They are:

**`TC_SBP_UI_001` — place a bet end to end and verify the receipt (UI),
in `tests/ui/test_place_bet_journey.py`.**
This is the only flow that debits a customer, and it is the one test that fails
if *any* component is broken: catalogue rendering, selection state, payout
arithmetic, the placement request, the balance write, and the receipt. It also
asserts the property most likely to be silently wrong — that the numbers shown
before submission are the numbers on the receipt afterwards, and that the
backend agrees with both. A discrepancy there is a financial defect, not a
display bug, and no cheaper test catches it.

**`TC_SBP_BET_B2`/`B4` — stake boundaries enforced at the API (API),
in `tests/api/test_place_bet.py`.**
Section 4.1 of the specification marks every stake rule as "UI + API". A rule
enforced only in the browser is not enforced: a scripted client, devtools, or a
stale tab bypasses it in seconds. Testing €0.99 / €1.00 / €100.00 / €100.01
directly against `POST /api/place-bet` targets the exact defect class that
dominates this kind of rule — an off-by-one in a comparison operator — at the
layer where the money actually moves. Each case runs in milliseconds and needs
no browser, which is why the whole matrix can sit in every pull request.

Together they cover the two axes that matter: *does the happy path hold end to
end*, and *does the system defend itself when the front end is not in the way*.
The repository ships considerably more than two tests, but these are the two
that would be kept if only two could run.

## 2. What was deliberately left manual

**The failure path and the error modal (TP-05).** The specification's failure
behaviour is real and important — **Rebet** retries, **Close** and **X** discard —
but there is no documented way to make placement fail on demand. Automating it
would mean either network interception that tests the mock rather than the
product, or retrying until the backend happens to fail, which is a flaky test
wearing a useful test's clothes. A flaky test in a money-critical suite is worse
than no test: it trains the team to ignore red. This becomes automatable the day
the backend offers a deterministic failure trigger.

**Visual and layout correctness.** "The bet slip is fixed to the right-hand
side", spacing, and responsive behaviour are cheap for a human to judge and
expensive and brittle to encode in Selenium assertions. If this needs coverage,
it belongs in visual-diff tooling, not here.

**Exploratory testing around the slip.** Double submission, mid-placement
refresh, back-button behaviour, and paste-versus-type in the stake field are
where undocumented defects live. That is human work by definition; automation
only locks in the ones already found.

**Accessibility and cross-browser.** Out of the assignment's scope (desktop
Chrome only), and better served by dedicated tooling than by this suite.

## 3. Top recommendations if this project scaled

**1. Enforce every money invariant server-side, atomically.**
Four of the most severe defects found (BUG-012, 014, 015, 019 - all Critical)
share one cause: the backend does not enforce the rules it claims to. Reset
reports a balance it never persists; negative stakes are accepted and inflate
the balance; a stake can drive the balance negative; two simultaneous bets can
both succeed. Every balance mutation needs one atomic, server-side check
(stake > 0, stake ≤ balance, one in-flight bet per user via a real lock, not a
race-prone read-then-write) before any further UI work is worth doing.

**2. Resolve the specification conflicts before writing more tests.**
Ten are documented in `docs/02` - four are outright contradictions (the stake
minimum alone is stated three different ways). Each is a place where a test
asserting the "wrong" reading looks like a product bug; scenarios resting on
one are tagged `@spec_gap` so the cost stays visible instead of silent.

**3. Split the match list by status, on a real UTC instant.**
The catalogue is one list, past-fixtures-first, and a "today" fixture can't be
told apart from an in-progress one - worse, two punters in different
timezones can read the same date as different days, since `kickoffDate` has
neither a time nor a timezone (BUG-011/024/025). Fix: three groups - Past,
Today, Upcoming, each sorted for its purpose - backed by an ISO 8601 UTC
timestamp instead of a bare date.

**4. Give match and bet data one canonical representation.**
Two unrelated-looking defects turned out to be the same failure: `place-bet`
returns `currency: "USD"` while every other endpoint says `"EUR"` (BUG-013),
and the receipt shows the teams reversed from what the bet slip showed
seconds earlier (BUG-020). Same root cause both times - the same fact gets
re-derived independently in each code path instead of coming from one shared
type. A contract test against a single schema would catch either the moment
it drifts.

## 4. Verification status

Executed against the real, deployed application (2026-09-03), not only a local
mock: API 132/132 (119 passed, 13 xfailed) on two separate full runs; the UI
suite's fixes each individually confirmed live. 15 of the 25 documented
defects were only reachable by executing, not by reading - see the README's
"Verification status" for the two-pass methodology and
`docs/02_execution_and_bug_reports.md` for every defect's reproduction steps.
