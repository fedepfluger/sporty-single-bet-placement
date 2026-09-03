# Execution Results & Bug Reports

> **Status: executed (2026-09-03).**
> Section 2 holds the ten defects found by reviewing the two documents against
> each other, before the application was opened. Section 3 holds fifteen
> further defects found by executing against the real application: nine from
> the API suite run, four from driving the real UI with Selenium, and two
> (BUG-024, BUG-025) from inspecting the deployed frontend bundle after
> follow-up questions raised the possibility of a third match state and of
> timezone handling - all reproduced independently outside the framework
> (`curl` for the API, direct DOM and
> bundle inspection for the frontend), with an `@pytest.mark.xfail` marker in
> the code for every one that a specific test can currently exercise.
>
> Final counts against the live application: the API suite is 132/132
> accounted for (119 passed, 13 xfailed, confirmed on two separate full runs).
> The UI suite's code fixes are individually confirmed (11 passed, 4 xfailed
> on a full run with no network issues; the remaining tests were re-verified
> in isolation after being fixed); later full reruns hit intermittent DNS
> resolution failures from this sandbox's network, unrelated to the
> application or the test code - see the note at the end of this section.
>
> Reviewing the specification first was not a substitute for execution: four of
> the section-2 defects are outright contradictions between sections, and two
> of those (BUG-004, BUG-007) would have sent the automation down the wrong
> path. Execution then found problems no amount of reading could have: BUG-012
> (reset reports a balance it never persists), BUG-014/015/019 (negative
> stakes, a balance that goes negative, and no real concurrency protection),
> and BUG-020 (the receipt reverses home and away) are defects only running
> requests and driving the real UI could reveal.

---

## 1. How execution will be run

| Scenario | Layer | How |
|----------|-------|-----|
| TP-01 Place a bet end to end | UI | Manually first, then `pytest -m "smoke and ui"` |
| TP-02 Stake boundaries at the API | API | `pytest -m "api and boundary"` |
| TP-03 Insufficient balance | UI + API | `pytest -k insufficient` |

Exploratory time-box: 20 minutes around the bet slip, focused on the
in-progress → resolution transition, double submission, and refreshing the page
mid-placement.

Evidence: Allure attaches the request/response pair for every API call and a
screenshot plus the severe browser console errors for every UI failure, so each
report below can cite a run rather than a recollection.

---

## 2. Defects found before execution (specification review)

These are real, reportable defects: an ambiguous specification is a defect in the
artefact the whole team builds and tests against, and it costs more the later it
is found — every one of these would otherwise surface as an argument about whether
a failing test is a product bug.

| ID | Title | Severity | Type |
|----|-------|----------|------|
| BUG-001 | Stake minimum stated as three different values | High | Contradiction |
| BUG-002 | Error response bodies are not specified | Medium | Gap |
| BUG-003 | 409 lock has no defined lifetime | Medium | Gap |
| BUG-004 | Receipt needs a Bet ID and timestamp the API never returns | High | Contradiction |
| BUG-005 | Match list must show a kickoff time the API does not provide | Medium | Contradiction |
| BUG-006 | Filters have no API surface | Medium | Gap |
| BUG-007 | "Only one bet active at a time" has two incompatible readings | High | Ambiguity |
| BUG-008 | No validation rule maps to a status code | Medium | Gap |
| BUG-009 | "Extra fields **may** be ignored" is non-normative | Low | Wording |
| BUG-010 | The two documents list different receipt fields | Low | Inconsistency |

### BUG-001 — Stake minimum is specified as three different values
**Severity:** High
**Type:** Specification defect

**Reproduction steps**
1. Read *Feature Specification* §3 Business Rules → "Stake min (per bet) **€1.00**".
2. Read §4.1 Stake Validation → "Minimum **€1.01** (positive values)".
3. Read §4.4 UI Error Messaging → "Minimum stake is **€1.00**".

**Expected vs actual**
- *Expected:* one authoritative minimum stake.
- *Actual:* three statements, of which §4.1 contradicts the other two.

**Business impact** A €1.00 stake is either the most common valid bet or an
invalid one, and nothing in the document decides which. Front end and back end
are being built from the same ambiguous source, so the two layers can disagree
in production while both "match the spec" — and any test asserting this boundary
is a coin toss. Given that §4.4 fixes the customer-facing copy at €1.00, that is
the reading the automation adopts.

**Likely root cause** §3 sets the *minimum odds* at 1.01. The §4.1 stake row
reads "Minimum €1.01", the same figure. The most economical explanation is that
the stake row was copied from the odds row, which would make §3 and §4.4 correct
and §4.1 the typo. Worth confirming before either value is treated as settled.

**Evidence** Encoded as `TC_SBP_BET_B1` in
`tests/api/test_place_bet.py::test_the_minimum_stake_is_accepted`, marked
`@pytest.mark.spec_gap` with the conflict quoted in its docstring, so a future
failure is read as "the spec was resolved the other way", not as flakiness.

---

### BUG-002 — Error response bodies are not specified
**Severity:** Medium
**Type:** Specification gap

**Reproduction steps**
1. Read §5.3 "Expected error classes": six status codes are listed (400, 401,
   405, 409, 422, 500).
2. Look for the shape of the body accompanying them. There is none.

**Expected vs actual**
- *Expected:* an error envelope — a field name, a machine-readable code, and
  whether validation failures are reported per field.
- *Actual:* status codes only.

**Business impact** The front end cannot map a 422 to the specific message §4.4
requires ("Minimum stake is €1.00" vs "Insufficient balance") without guessing
at the payload. Any client-side mapping built on that guess breaks the first
time the backend rewords a field. It also blocks automated assertions on the
*reason* for a rejection, which is what makes a negative test meaningful rather
than merely counting a status code.

**Evidence** `config/schemas/error.schema.json` documents the assumption the
suite is forced to make: any JSON object carrying `error`, `message`, `errors`
or `detail` is accepted.

---

### BUG-003 — "Bet already in progress" (409) has no defined lifetime
**Severity:** Medium
**Type:** Specification gap

**Reproduction steps**
1. Read §5.3: `409 bet already in progress (same user)`.
2. Look for when the in-progress lock is released, or what happens if a
   placement request is abandoned mid-flight.

**Expected vs actual**
- *Expected:* a stated lock lifetime and release condition.
- *Actual:* the condition is named but never bounded.

**Business impact** If the lock is not released when a request dies (a closed
tab, a dropped connection), a punter is locked out of betting for an undefined
period with no way to clear it themselves — a direct revenue loss and a support
call. This is also the rule that stops the same balance being spent twice, so
its exact semantics matter more than most.

**Evidence** `tests/api/test_place_bet.py::test_two_simultaneous_bets_cannot_both_be_accepted`
(`TC_SBP_BET_C1`) asserts the property that holds under every reading of the
spec: two simultaneous placements must not both succeed.

---

---

### BUG-004 — The receipt must show a Bet ID and a timestamp the API never returns
**Severity:** High
**Type:** Contradiction between sections

**Reproduction steps**
1. Read *Feature Specification* §2.4: the receipt "must show" **Bet ID**, Match
   details, Selection, Stake, Odds at placement, Potential payout and
   **Placement timestamp**.
2. Read §5.3, the 200 response of `POST /api/place-bet`: `message`, `matchId`,
   `selection`, `stake`, `odds`, `payout`, `balance`, `currency`.
3. Look for `betId` or any timestamp field. Neither exists.

**Expected vs actual**
- *Expected:* every value the receipt must display is available from the
  placement response.
- *Actual:* two of the seven mandated fields have no source. The front end can
  only fabricate them client-side.

**Business impact** The Bet ID is the customer's reference for a bet — what they
quote to support and what reconciles against the ledger. An id invented in the
browser is not a reference to anything: it is not stored server-side, differs
between two tabs, and cannot be looked up. A punter disputing a bet would have a
receipt whose identifier the platform has never seen. The same applies to the
timestamp, which is the only evidence of *when* odds were struck.

**Confirmed by execution** Placing a real bet shows a receipt reading `Bet ID
#B-36491` and `Today, 01:47 PM` — both rendered with real, stable element ids
(`#modal-success-bet-id`, `#modal-success-placed-at`). The `POST
/api/place-bet` response for that same request carried neither field. The
frontend fabricates both client-side, exactly as predicted before the app was
opened.

**Evidence** `tests/ui/test_place_bet_journey.py::test_place_a_bet_end_to_end_and_receive_a_consistent_receipt`
asserts all seven fields via `Receipt.missing_fields()`, because §2.4 requires
them; the Selection field is genuinely absent in the real markup (BUG-020).
[`docs/screenshots/06_receipt_after_placement.png`](screenshots/06_receipt_after_placement.png)
shows the fabricated Bet ID and timestamp live.

---

### BUG-005 — The match list must show a kickoff time the API does not provide
**Severity:** Medium
**Type:** Contradiction between sections

**Reproduction steps**
1. Read §2.1: each match shows a "kickoff **date/time** label".
2. Read §5.3, `GET /api/matches`: `kickoffDate: string (YYYY-MM-DD)`.

**Expected vs actual**
- *Expected:* the field backing the label carries a time.
- *Actual:* it carries a date only. There is no time to render.

**Business impact** Kickoff time is how a punter knows whether a market is about
to close. Two fixtures on the same day are indistinguishable, and a bet placed
believing kickoff is hours away may be seconds from it. Either §2.1 overstates
the requirement or the API field is under-specified; both readings need a
different implementation.

**Evidence** `TC_SBP_UI_007` asserts each card renders a non-empty kickoff label,
which passes for a date-only label. It cannot assert a time that the contract
does not promise.

---

### BUG-006 — The filters have no API surface
**Severity:** Medium
**Type:** Specification gap

**Reproduction steps**
1. Read §2.6: a date filter (single day or inclusive range) and an odds filter
   (inclusive min/max).
2. Read §5.3, `GET /api/matches`: no query parameters are documented.

**Expected vs actual**
- *Expected:* either documented filter parameters, or an explicit statement that
  filtering is client-side over the full catalogue.
- *Actual:* neither. The behaviour is left to the implementation.

**Business impact** The two readings differ in what breaks. Client-side means the
whole catalogue ships on every load and filtering stops working the moment the
catalogue is paginated. Server-side means there are undocumented parameters, so
nobody can test them, and unknown parameters are exactly where injection and
error-handling defects hide. It also leaves an unanswered money-adjacent
question: if a filter hides the match currently in the bet slip, does the
selection survive?

**Evidence** `tests/ui/test_filters.py` drives the filters through the browser
only — the sole layer the specification defines. `TC_SBP_MATCHES_E1` is marked
`@spec_gap` because it has to guess what an unknown query parameter should do.

---

### BUG-007 — "Only one bet can be active at a time" has two incompatible readings
**Severity:** High
**Type:** Ambiguity across documents

**Reproduction steps**
1. Read the assignment's Domain Context, *Bet Slip*: "Only one bet can be active
   at a time."
2. Read *Feature Specification* §2.2: "Shows one active **selection** at a time."
3. Read §5.3: `409 bet already in progress (same user)`.

**Expected vs actual**
- *Expected:* one statement of what may only exist once — a slip selection, an
  in-flight placement request, or an unsettled bet.
- *Actual:* three statements that support three different rules.

**Business impact** Under the strictest reading — one *unsettled bet* per user —
a punter could never place a second bet, because no settlement flow is specified
anywhere. That would make the product unusable, and it would invalidate any test
that places bets in sequence. Under the loosest reading, 409 only guards
concurrent requests and sequential betting is unlimited. The difference is the
core of the product, and it is decided nowhere.

**Evidence** The suite adopts the in-flight reading: tests place bets in sequence
and `TC_SBP_BET_C1` asserts only the invariant that survives every reading — two
simultaneous placements must not both be accepted. If the strict reading turns
out to be correct, most of the place-bet matrix would need to reset state between
cases rather than only the balance.

---

### BUG-008 — No rule maps to a status code
**Severity:** Medium
**Type:** Specification gap

**Reproduction steps**
1. Read §4.1 and §4.2. Every row's expected result is a verb: "reject",
   "blocked/rejected", "show/reject".
2. Read §5.3, which lists 400, 401, 405, 409, 422 and 500.
3. Try to determine which code a non-numeric stake produces: `400 malformed
   payload` or `422 semantic validation failures (selection/stake/match)`.

**Expected vs actual**
- *Expected:* each validation rule names the status it returns.
- *Actual:* the codes exist and the rules exist, with nothing joining them.

**Business impact** The front end cannot decide whether a rejection is the user's
fault or a bug, so it cannot choose between the copy §4.4 mandates and a generic
failure. For testing it is worse: an assertion that accepts "400 or 422" passes
whichever the backend does, which means it can never catch the backend changing
its mind.

**Evidence** Several tests assert `assert_status(response, 400, 422)` for exactly
this reason — see `test_non_numeric_stakes_are_rejected` and
`test_invalid_selections_are_rejected`. Each one is a weaker check than it should be.

---

### BUG-009 — "Extra fields may be ignored by the API" is not a requirement
**Severity:** Low
**Type:** Non-normative wording

**Reproduction steps**
1. Read §5.3, request body of `POST /api/place-bet`: "Extra fields **may** be
   ignored by the API."

**Expected vs actual**
- *Expected:* "must be ignored" or "must be rejected".
- *Actual:* "may", which permits both and mandates neither.

**Business impact** This is the sentence that decides whether a client can send
its own `payout` or `balance` and have the backend honour it. Read permissively,
it licenses a serious defect. Nothing in the document forbids it.

**Evidence** `TC_SBP_BET_004` asserts the safe reading — a bet carrying
`payout`, `balance`, `odds` and `isAdmin` is priced and debited by the backend's
own numbers. It is marked `@security` rather than `@spec_gap` because no reading
of the specification should allow the alternative.

---

### BUG-010 — The two documents list different receipt fields
**Severity:** Low
**Type:** Inconsistency across documents

**Reproduction steps**
1. *Feature Specification* §2.4 lists seven fields, including **Selection**.
2. The assignment's Domain Context, *Bet Receipt*, lists six: "the bet ID, match,
   stake, odds, potential payout, and timestamp" — no selection.

**Expected vs actual**
- *Expected:* one authoritative field list.
- *Actual:* two lists differing by the field that says *what was actually backed*.

**Business impact** Small in isolation, but Selection is the one field that
distinguishes a winning receipt from a losing one. A receipt built from the
shorter list would show the match and the stake without saying which outcome the
punter took.

**Evidence** The suite asserts the longer list, on the grounds that the Feature
Specification is the more specific document.

**Confirmed by execution** The real receipt implements the shorter, six-field
Domain Context list: no Selection field is rendered anywhere in the success
modal. See BUG-020 for the full evidence, including that the Match field also
reverses home and away.


---

## 3. Execution findings — real defects, found by running the automated suite

**Status: executed.** With a real `USER_ID` and permission to run against the
live application (2026-09-03), the full API suite (`pytest tests/api`) was run
against `https://qae-assignment-tau.vercel.app`. 119 of 132 tests passed; 13
failed, tracing back to **9 distinct defects**, all reproduced independently
with `curl` outside the framework so the framework itself is not the suspect.

The UI suite (`pytest tests/ui`) was then driven with real Selenium against
the same live application. The DOM carries no `data-testid` attributes at
all - `tests/app_actions/ui/locators.py` was rewritten from real, inspected
markup rather than guesses - and driving it surfaced **4 further defects**
(BUG-020 to BUG-023), plus two genuine bugs in the test code itself (a stale
match index, an invalid XPath expression) that real execution catches and a
mock never would. Once both were fixed, every remaining failure traced to
either a real application defect or a test premise the real UI disproved (the
stake field sanitises invalid keystrokes rather than rejecting them outright -
not a defect, a design choice the test had assumed wrong).

Every affected test is marked `@pytest.mark.xfail` with the bug id, so the
suite stays green and self-documenting: if a fix lands, the test flips to an
unexpected pass and is the signal to remove the marker.

| ID | Title | Severity |
|----|-------|----------|
| BUG-011 | The catalogue serves 74 past fixtures before any upcoming one | High |
| BUG-012 | `POST /api/reset-balance` reports a balance it does not persist | Critical |
| BUG-013 | `POST /api/place-bet` returns `currency: "USD"`, never EUR | Medium |
| BUG-014 | Negative stakes are accepted and produce a negative payout | Critical |
| BUG-015 | A stake can drive the balance negative | Critical |
| BUG-016 | A malformed request body crashes the server (HTTP 500) | High |
| BUG-017 | An empty request body returns 422, not the documented 400 | Low |
| BUG-018 | `GET /api/place-bet` is accepted; the endpoint is not POST-only | Medium |
| BUG-019 | Two simultaneous bets are both accepted; no 409 protection exists | Critical |
| BUG-020 | The receipt reverses home/away and omits Selection | High |
| BUG-021 | The displayed balance does not refresh after a successful bet | Medium |
| BUG-022 | An inverted odds filter range is silently accepted, no feedback | Low |
| BUG-023 | The bet slip drops its balance readout once a selection is active | Low |
| BUG-024 | A fixture kicking off "today" cannot be told apart from one in progress | High |
| BUG-025 | kickoffDate has no timezone anchor - same fixture, different day per viewer | High |

---

### BUG-011 — The catalogue serves 74 past fixtures before any upcoming one
**Severity:** High
**Type:** Executed defect (confirms BUG-005/BUG-006's premise directly)

**Reproduction steps**
1. `GET /api/matches` with a valid `x-user-id`.
2. Compare each `kickoffDate` to today (2026-09-03).

**Expected vs actual**
- *Expected:* Feature Specification §2.1, "Display **upcoming** football
  matches"; Domain Context, "Event Type: Upcoming/Pre-match events only".
- *Actual:* 103 matches returned; **74 have already kicked off** (as early as
  2026-02-27), all ordered before the 29 genuinely upcoming ones. The first
  upcoming fixture sits at index 74.

**Business impact** Any client that trusts "the first match in the list" -
which is a completely reasonable assumption given the spec - places a bet on a
fixture whose result is already known. This project's own `first_match()`
helper did exactly that until this run exposed it; every test built on "grab a
match and bet on it" was silently betting on Manchester Utd vs Chelsea from
February. Fixed here by filtering to `kickoffDate >= today` (see the App
Actions changelog below); the API itself still returns the past fixtures.

**Evidence** `tests/api/test_get_matches.py::test_catalogue_respects_the_documented_business_rules`
(`TC_SBP_MATCHES_002`), run against the real API, lists all 74 offending ids.
[`docs/screenshots/01_match_list_past_before_upcoming.png`](screenshots/01_match_list_past_before_upcoming.png)
shows it live: every visible card badged "PAST".

---

### BUG-012 — `POST /api/reset-balance` reports a balance it does not persist
**Severity:** Critical
**Type:** Executed defect

**Reproduction steps**
```bash
curl -s -X POST -H "x-user-id: $UID" -H "Content-Type: application/json" -d '{}' \
  https://qae-assignment-tau.vercel.app/api/reset-balance
curl -s -H "x-user-id: $UID" https://qae-assignment-tau.vercel.app/api/balance
```
Repeated 3 times in a row.

**Expected vs actual**
- *Expected:* Specification §5.3, "Response body and persisted state must be
  consistent after reset."
- *Actual:* **Every single time**, `reset-balance` answers
  `{"balance":125.5,...}` and the immediately following `GET /api/balance`
  answers `{"balance":120,...}`. 100% reproducible, not a timing race.

**Business impact** This is the one endpoint every other test - manual or
automated - relies on for a known starting state. If the balance it reports is
not the balance it wrote, no test that asserts "balance decreased by exactly
the stake" can trust its own baseline, and a support agent trying to explain a
punter's balance has no reliable source of truth to reset to.

**Evidence** `tests/api/test_reset_balance.py::test_the_reset_response_and_the_persisted_state_agree`
and `::test_resetting_twice_is_idempotent`, plus `test_get_balance.py::test_a_freshly_reset_balance_reports_the_initial_amount`.

---

### BUG-013 — `POST /api/place-bet` returns `currency: "USD"`, never EUR
**Severity:** Medium
**Type:** Executed defect

**Reproduction steps** Place any valid bet and read the `currency` field of
the 200 response. `GET /api/balance` and `POST /api/reset-balance` both
correctly answer `"EUR"` for the same account in the same session.

**Expected vs actual**
- *Expected:* Specification §5.3 pins `currency: "EUR"` on every response,
  and §3 fixes the platform currency at EUR.
- *Actual:* `place-bet`'s response hardcodes (or defaults to) `"USD"` every
  time, while every other endpoint says `"EUR"`.

**Business impact** A receipt or a downstream ledger reading this field would
record the wrong currency for every settled bet - a real reconciliation and
regulatory problem for a business whose only listed currency is EUR.

**Evidence** `tests/api/test_place_bet.py::test_place_a_valid_single_bet`
fails `assert_schema(response, "place_bet")` specifically on this field.

---

### BUG-014 — Negative stakes are accepted and produce a negative payout
**Severity:** Critical
**Type:** Executed defect

**Reproduction steps** `POST /api/place-bet` with `stake: -1` or `stake: -50`.

**Expected vs actual**
- *Expected:* §4.1, stake "Must be numeric" / "Minimum €1.01 (positive
  values)" - UI + API layer, rejected either way.
- *Actual:* HTTP 200. `stake: -1` returns `payout: -2.35` and *increases* the
  balance; `stake: -50` returns `payout: -117.5` and increases the balance by
  117.5. Note the boundary tests for `0`, `0.01` and `0.99` **are** correctly
  rejected with 422 - only negative values slip through, which points at a
  validation that checks magnitude but not sign.

**Business impact** This is a direct exploit: a negative stake is a
disguised, unlimited-size credit to the account. Nothing about "positive
values only" is enforced once the sign flips.

**Evidence** `tests/api/test_place_bet.py::test_stakes_below_the_minimum_are_rejected[-1]` and `[-50]`.

---

### BUG-015 — A stake can drive the balance negative
**Severity:** Critical
**Type:** Executed defect

**Reproduction steps** With a balance below the stake being placed, place a
valid (positive, in-range) bet for more than the remaining balance.

**Expected vs actual**
- *Expected:* §4.1, "Stake Must not exceed available balance" - UI + API,
  rejected as insufficient balance.
- *Actual:* HTTP 200. A €50 stake against a lower balance was accepted and
  left the account at **balance: -30**.

**Business impact** The single rule that stops a punter going into debt does
not hold. Combined with BUG-014, the account can be pushed to an arbitrary
negative balance in two different ways.

**Evidence** `tests/api/test_place_bet.py::test_a_stake_above_the_remaining_balance_is_refused`.

---

### BUG-016 — A malformed request body crashes the server (HTTP 500)
**Severity:** High
**Type:** Executed defect

**Reproduction steps** `POST /api/place-bet` with a body that is not valid
JSON (plain text, or truncated JSON).

**Expected vs actual**
- *Expected:* §5.3, "malformed/non-object payloads -> 400"; and the
  cross-cutting rule that invalid input must never produce a 5xx.
- *Actual:* HTTP 500, `{"error":"internal_server_error","message":"Unable to
  process request."}` - an unhandled exception, not a validation response.

**Business impact** A 500 on bad input is the textbook signature of an
unhandled exception, which is the class of bug most likely to also be
triggerable at scale (a crash loop) or to leak a stack trace in a less
defensive environment than this one.

**Evidence** `tests/api/test_place_bet.py::test_malformed_payloads_are_rejected[plain_text]` and `[truncated_json]`.

---

### BUG-017 — An empty request body returns 422, not the documented 400
**Severity:** Low
**Type:** Executed inconsistency

**Reproduction steps** `POST /api/place-bet` with an empty body.

**Expected vs actual**
- *Expected:* §5.3 lists "malformed/non-object payloads" under 400.
- *Actual:* HTTP 422, `{"error":"invalid_match_id","message":"Match id is
  invalid."}` - the server appears to treat a missing body as `{}` and run
  semantic validation on it, rather than rejecting it at the parse stage.

**Business impact** Low on its own; grouped with BUG-008 it confirms that
status-code selection is inconsistent rather than unspecified - the same
"missing field" condition gets 422 here and would get 400 if the body were
merely truncated JSON (BUG-016), which is the opposite of predictable.

**Evidence** `tests/api/test_place_bet.py::test_an_empty_body_is_rejected`.

---

### BUG-018 — `GET /api/place-bet` is accepted; the endpoint is not POST-only
**Severity:** Medium
**Type:** Executed defect

**Reproduction steps** `GET /api/place-bet` with a valid `x-user-id`.

**Expected vs actual**
- *Expected:* §5.3, §4.3 "Unsupported HTTP method -> method-not-allowed
  response" (405).
- *Actual:* HTTP 200, empty JSON object `{}`. No money moves, but the route
  itself does not enforce its documented verb.

**Business impact** Low direct risk here since the response is empty, but a
route that silently accepts an undocumented method is one CORS, caching or
proxy layer away from a real problem, and it means the 405 contract cannot be
trusted anywhere else in the API without checking each endpoint individually.

**Evidence** `tests/api/test_place_bet.py::test_unsupported_http_method_is_rejected[GET]`.

---

### BUG-019 — Two simultaneous bets are both accepted; no 409 protection exists
**Severity:** Critical
**Type:** Executed defect (resolves BUG-007's open question with a concrete answer)

**Reproduction steps** Fire two `POST /api/place-bet` requests for the same
user at the same time (`ThreadPoolExecutor`, two workers), repeated across
several runs.

**Expected vs actual**
- *Expected:* §5.3, `409 bet already in progress (same user)`.
- *Actual:* Intermittent, not consistent. One run: both requests return HTTP
  200 - both bets accepted. A repeat run: only one succeeded. Whatever reading
  of BUG-007 one takes, there is no reliable lock: the outcome depends on
  request timing rather than a guaranteed 409, which is a race a punter (or
  script) can win by chance to double up a bet.

**Business impact** This is the concrete, executed version of the risk BUG-007
could only describe hypothetically. It is a real double-spend path against
the account balance, and the highest-value thing to fix before this endpoint
carries real money.

**Evidence** `tests/api/test_place_bet.py::test_two_simultaneous_bets_cannot_both_be_accepted`.


---

### BUG-020 — The receipt reverses home and away, and omits Selection
**Severity:** High
**Type:** Executed defect

**Reproduction steps**
1. Select HOME on Sevilla vs Valencia (Sevilla is `homeTeam` per `GET
   /api/matches`; the bet slip itself renders "Sevilla vs Valencia").
2. Place the bet and read the success modal.

**Expected vs actual**
- *Expected:* Domain Context, "Match Ordering" - "This convention carries
  through to the bet receipt." Feature Specification §2.4 lists Selection as
  a required receipt field.
- *Actual:* The receipt's Match field reads **"Valencia vs Sevilla"** - home
  and away swapped relative to both the API and the bet slip shown seconds
  earlier. The Selection field (HOME/DRAW/AWAY) is not rendered anywhere in
  the modal at all; only Bet ID, Match, Stake, Odds, Potential Payout and a
  timestamp appear - six fields, matching the assignment's Domain Context list
  rather than the Feature Specification's seven-field list. Resolves BUG-010's
  open question with a concrete answer: the implementation follows the
  shorter list, and swaps team order doing it.

**Business impact** A receipt that silently reverses which team was home
undermines the one thing a receipt exists for - proof of exactly what was
backed. Paired with the missing Selection field, a punter's own receipt
cannot fully answer "what did I bet on?"

**Evidence** `tests/ui/test_place_bet_journey.py::test_place_a_bet_end_to_end_and_receive_a_consistent_receipt`
(`TC_SBP_UI_001`) marked `xfail`.
[`docs/screenshots/02_selection_in_slip.png`](screenshots/02_selection_in_slip.png)
shows "Sevilla vs Valencia" (correct order) in the slip;
[`06_receipt_after_placement.png`](screenshots/06_receipt_after_placement.png)
shows the same bet's receipt reading "Valencia vs Sevilla" seconds later.

---

### BUG-021 — The displayed balance does not refresh after a successful bet
**Severity:** Medium
**Type:** Executed defect

**Reproduction steps**
1. Note the header/bet-slip balance.
2. Place a valid bet successfully.
3. Read the header and bet-slip balance again, without reloading the page.
4. Reload the page and read them a third time.

**Expected vs actual**
- *Expected:* Domain Context, "Balance ... Decreases by the stake amount when
  a bet is placed. The balance is shared across the header and the bet slip."
- *Actual:* Immediately after a successful €10 bet, both the header and the
  bet slip still read the pre-bet balance. `GET /api/balance` confirms the
  backend correctly deducted the stake. Only a full page reload makes the UI
  catch up - the success path never re-fetches or locally updates the
  balance it just spent.

**Business impact** A punter who places a second bet without refreshing sees
a stale, higher balance than they actually have, and may attempt (or believe
they can afford) a stake the account can no longer cover.

**Evidence** `tests/ui/test_place_bet_journey.py::test_place_a_bet_end_to_end_and_receive_a_consistent_receipt`
asserts `header_balance() == balance_before - stake` right after closing the
receipt, with no reload - exactly the path this bug breaks. The before/after
pair is captured live:
[`07_balance_after_closing_receipt.png`](screenshots/07_balance_after_closing_receipt.png)
(still €120.00 right after a €10 bet) vs
[`08_balance_after_manual_reload.png`](screenshots/08_balance_after_manual_reload.png)
(correctly €110.00 after a manual reload).

---

### BUG-022 — An inverted odds filter range empties the list with no error, behind a stale count
**Severity:** Low
**Type:** Executed defect

**Reproduction steps** Open the odds filter, set Min €5.00 and Max €1.50
(inverted), click Apply.

**Expected vs actual**
- *Expected:* §2.6, "must reject invalid ranges with clear feedback."
- *Actual:* No error, no `role="alert"` element, nothing rejects the input -
  the filter chip happily reads "Odds: 5.00 - 1.50". The match list genuinely
  empties (correct, in a sense: no fixture has odds simultaneously ≥5.00 and
  ≤1.50) but the "Showing X matches" counter does not update to match - it
  keeps reading "Showing 103 matches" over a visibly empty list. See
  [`docs/screenshots/11_inverted_odds_filter_no_feedback.png`](screenshots/11_inverted_odds_filter_no_feedback.png).

**Business impact** Low - no money involved - but it is exactly the failure
mode the original test rationale called out, made worse by the stale counter:
a punter narrowing to an impossible range sees an empty page *captioned as
showing 103 matches*, which reads as "the site is broken" rather than "your
filter is invalid" - there is no path from what they see back to what they
did wrong.

**Evidence** `tests/ui/test_filters.py::test_an_inverted_odds_range_is_rejected_with_clear_feedback`
(`TC_SBP_UI_F1`) marked `xfail`.
[`docs/screenshots/11_inverted_odds_filter_no_feedback.png`](screenshots/11_inverted_odds_filter_no_feedback.png).


### BUG-023 — The bet slip drops its balance readout once a selection is active
**Severity:** Low
**Type:** Executed defect

**Reproduction steps** Open the betting page with an empty slip (balance is
shown at `#bet-slip-balance` in the slip header). Select any odds button.

**Expected vs actual**
- *Expected:* Domain Context, "Balance ... is shared across the header and
  the bet slip" - no qualifier about only while the slip is empty.
- *Actual:* The moment a selection exists, the slip header replaces its
  balance readout (`.betSlipBalance`) with a "Remove All" button. The header
  keeps showing the balance; the slip no longer does. Confirmed via direct
  DOM inspection: `#bet-slip-balance` is present with the empty slip and
  absent entirely once `.betSelectionCard` renders.

**Business impact** Minor - the header still shows the true balance - but it
means the one place a punter is actively looking while deciding a stake (the
slip itself) no longer confirms what they have to spend.

**Evidence** `tests/ui/test_place_bet_journey.py::test_the_header_and_the_bet_slip_always_show_the_same_balance`
(`TC_SBP_UI_002`) marked `xfail`.
[`docs/screenshots/09_slip_shows_balance_when_empty.png`](screenshots/09_slip_shows_balance_when_empty.png)
(balance shown, empty slip) vs
[`10_slip_balance_missing_once_selected.png`](screenshots/10_slip_balance_missing_once_selected.png)
(same page, one selection active, balance gone from the slip header - "Remove All" in its place).


### BUG-024 — A fixture kicking off "today" cannot be told apart from one already in progress
**Severity:** High
**Type:** Executed defect / data gap

**Reproduction steps**
1. `GET /api/matches` and inspect `kickoffDate` - confirmed a plain date
   (`YYYY-MM-DD`), no time component, and no `status` field of any kind: the
   full set of fields is `id, competition, kickoffDate, homeTeam, awayTeam,
   odds`.
2. Inspect the deployed frontend bundle
   (`https://qae-assignment-tau.vercel.app/assets/index-BAomKdAy.js`) for the
   function computing each card's status badge:
   ```js
   function statusLabel(date){
     const parsed = parseDate(date);
     if (!parsed) return "UPCOMING";
     const today = truncateToDay(new Date()), day = truncateToDay(parsed);
     return day < today ? "PAST" : isSameDay(day, today) ? "TODAY" : "UPCOMING";
   }
   ```
   (renamed from the minified `Cy`/`S0`/`Aa` for readability; logic unchanged).

**Expected vs actual**
- *Expected:* Feature Specification §2.1 lists a two-state distinction
  (upcoming vs not); Domain Context defines "Event Type: Upcoming/Pre-match
  events only (no live betting)" as an explicit scope boundary.
- *Actual:* The frontend's own code computes **three** states - PAST, TODAY,
  UPCOMING - which is itself evidence that its developers recognised the
  two-state model breaks down for the current day. A date-only `kickoffDate`
  cannot say whether a "today" fixture is still hours away or already live,
  and the API gives a test (or the frontend) no way to resolve that
  ambiguity - no kickoff time, no live/finished flag.

**Business impact** This is the concrete mechanism behind the spec's "no live
betting" rule being unenforceable for any fixture dated today: the backend
cannot tell a client whether such a fixture is safe to bet on, so any client
that treats "today" as bettable (as this project's own `first_match()` did
until this fix) risks placing a bet on a match already in progress or
finished - a real regulatory and trading-risk problem for a betting product,
not a cosmetic one. Not currently observable end-to-end: the live catalogue
has zero fixtures with `kickoffDate` equal to today (2026-09-03) at the time
of this run, so no request/response pair demonstrates the API's own behaviour
for a "today" bet. The fix here is precautionary, not a confirmed API-level
acceptance/rejection.

**Evidence** `tests/app_actions/api/betting_api_actions.py::first_match()` now
selects strictly `kickoffDate > today` (was `>=`); `tests/app_actions/ui/
components/match_list.py::first_upcoming_index()` now requires the status
badge to read exactly "UPCOMING" rather than merely "not PAST". Re-test once
a "today" fixture exists in the catalogue, by placing a bet on it directly via
`POST /api/place-bet` and recording the actual status code.


### BUG-025 — `kickoffDate` has no timezone anchor, so the same fixture can read as a different day for different viewers
**Severity:** High
**Type:** Data gap, confirmed from the deployed code (not independently
reproduced live across timezones - see Evidence)

**Reproduction steps**
1. `GET /api/matches`: `kickoffDate` matches `^\d{4}-\d{2}-\d{2}` only - no
   `T`, no UTC offset, no `Z` suffix. Confirmed against both
   `config/schemas/matches.schema.json` and the live response body.
2. The frontend's date-parsing logic (already captured verbatim for BUG-024)
   parses that string with `new Date(year, month-1, day)` and truncates "now"
   with `new Date(l.getFullYear(), l.getMonth(), l.getDate())` - JavaScript's
   **local-time** `Date` APIs. Neither `Date.UTC(...)` nor any `getUTC*`
   accessor appears anywhere in the status-badge logic.

**Expected vs actual**
- *Expected:* a fixture's kickoff is a single instant. Two punters anywhere in
  the world looking at the same match should each get a *correct* answer for
  "is this upcoming, today, or past" - correct relative to their own clock,
  once the instant is properly converted.
- *Actual:* there is no timezone information anywhere in the pipeline for a
  conversion to even be possible. Every viewer's browser takes the literal
  digits `"2026-09-06"` and compares them to *its own machine's* local
  calendar date, unconverted. This is not "off by the viewer's offset" - no
  conversion is attempted at all, so the badge a viewer sees depends on
  nothing but their own system clock's date, regardless of where in the world
  the actual kickoff instant falls. A 23:00 UTC kickoff, for example, is
  already the next calendar day across most of Europe while still "today"
  throughout the Americas; nothing in this pipeline could tell those two
  viewers apart even after BUG-024's time-of-day gap is closed, because a
  time without a timezone is exactly as ambiguous as a date without one.

**Business impact** Compounds BUG-024 rather than standing apart from it: even
a fix that adds a kickoff *time* is still unsafe for a global product unless
that time also carries a timezone, since the underlying defect is the same
missing concept - kickoffDate is a naive value with no reference frame, so
"today" is only ever "today according to whichever machine asked."

**Evidence** `config/schemas/matches.schema.json` (the pinned pattern);
BUG-024's captured frontend source (`S0`/`Aa`/`statusLabel`, this doc's
previous entry). Not re-verified by loading the app from a second timezone -
that would need a second physical/emulated locale, and the defect is already
conclusively demonstrated by the parsing code itself: a naive local-time
`Date` constructor cannot produce a timezone-correct answer regardless of
which machine runs it.


## 4. Template for further findings

Copy this block per defect found while executing.

### BUG-0NN — <one-line title>
**Severity:** Critical / High / Medium / Low

**Reproduction steps**
1.
2.
3.

**Expected vs actual**
- *Expected:*
- *Actual:*

**Business impact** <one sentence on the user or business consequence>

**Evidence** <screenshot path, Allure run, or a note>

---

### Exploratory checklist to work through

- [ ] Double-click **Place Bet** — is the second submission blocked, or is the
      balance debited twice?
- [ ] Refresh the page mid-placement — what does the balance read afterwards?
- [ ] Place a bet, then use the browser Back button — does a stale slip return?
- [ ] Open the same `user-id` in two tabs and place a bet in each — does the 409 fire?
- [ ] Paste `100.00` into the stake field rather than typing it — is validation still applied?
- [ ] Type `1.005` — is the third decimal rejected on input or only on submit?
- [ ] Leading zeros (`0010.00`) and a leading `+` (`+10.00`).
- [ ] Change the `user-id` query parameter to another value — whose balance appears?
- [ ] Check the receipt timestamp's timezone against local time.
- [ ] Confirm the home team is always rendered first, and that the receipt keeps
      the same order (Domain Context, "Match Ordering").
