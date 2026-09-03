# Test Plan — Single Bet Placement

**Scope:** desktop web, football only, pre-match single bets.

**Source:** *Feature Specification — Single Bet Placement*, sections 2–5.

**Out of scope:** live betting, accumulators, other sports, mobile-specific UX.

## How this set was chosen

The feature has one irreversible action — `POST /api/place-bet` — and everything
else exists to feed it. Risk therefore concentrates in three places:

1. **Money correctness.** Stake, odds and payout must agree across the slip, the
   backend and the receipt. A discrepancy here is a direct financial loss and a
   regulatory problem, not a cosmetic bug.
2. **Validation depth.** The specification requires stake rules to hold at
   *both* layers (section 4.1, "UI + API"). A rule enforced only in the browser
   is not enforced at all.
3. **State transitions.** Placement has an in-progress state that must always
   resolve (section 2.3), and a shared balance that must move exactly once.

Boundary conditions cluster around the stake (€1.00 / €100.00 / 2 decimals /
available balance), so that is where the boundary scenarios sit.

## Prioritised scenarios

| ID | Title | Priority |
|----|-------|----------|
| TP-01 | Place a valid bet end to end and receive a consistent receipt | Critical |
| TP-02 | Stake boundaries are enforced at the API, not only in the UI | Critical |
| TP-03 | A stake above the available balance is refused and no money moves | Critical |
| TP-04 | Selecting a new outcome replaces the previous selection | High |
| TP-05 | Placement always resolves, and a failure clears down cleanly | High |
| TP-06 | An invalid odds filter range is rejected with clear feedback | Medium |

---

### TP-01 — Place a valid bet end to end and receive a consistent receipt
**Priority:** Critical
**Risk rationale:** This is the revenue path and the only flow that debits a
customer. Its failure mode is not "a page looks wrong" but "the punter is
charged for a bet they did not get, or gets a bet they were not charged for".
It also transits every component at once — catalogue, slip, API, balance,
receipt — so it is the single highest-information test in the set.

**Steps**
1. Open the application with a valid `user-id` and note the header balance.
2. Click the `1` (home) odds button on the first match; note the odds shown.
3. Enter a stake of `10.00` in the bet slip.
4. Check the potential payout displayed in the slip.
5. Press **Place Bet**.
6. Read every field on the success receipt, then close it.

**Expected result**
- The slip payout equals `stake × odds` rounded to cents.
- Placement shows the `Placing...` state and resolves to a success receipt.
- The receipt shows bet ID, match, selection, stake, odds, payout and timestamp,
  and its stake/odds/payout match what the slip showed before submission.
- The balance drops by exactly `10.00` in both the header and the slip.
- Closing the receipt leaves no active selection.
- `GET /api/balance` agrees with the balance on screen.

**Evidence (executed 2026-09-03)** Fails, on three separate points documented
as defects rather than as a broken test:
- [`docs/screenshots/01_match_list_past_before_upcoming.png`](screenshots/01_match_list_past_before_upcoming.png) —
  step 1's "first match" is a fixture from February (BUG-011).
- [`docs/screenshots/05_valid_stake_payout_computed.png`](screenshots/05_valid_stake_payout_computed.png) —
  steps 2-4: selection and payout preview both correct.
- [`docs/screenshots/06_receipt_after_placement.png`](screenshots/06_receipt_after_placement.png) —
  step 6: the receipt reads "Valencia vs Sevilla", reversed from "Sevilla vs
  Valencia" shown in the slip one screenshot earlier, and has no Selection
  field at all (BUG-020).
- [`docs/screenshots/07_balance_after_closing_receipt.png`](screenshots/07_balance_after_closing_receipt.png)
  vs [`08_balance_after_manual_reload.png`](screenshots/08_balance_after_manual_reload.png) —
  the balance does not drop until the page is manually reloaded (BUG-021).

---

### TP-02 — Stake boundaries are enforced at the API, not only in the UI
**Priority:** Critical
**Risk rationale:** Section 4.1 marks every stake rule as "UI + API". A browser
control is trivially bypassed (devtools, a scripted client, a stale tab), so a
rule that lives only in the front end is an open door to stakes outside the
licensed limits. Boundary values are used because off-by-one errors in
comparison operators are the single most common defect class in this area.

**Steps**
For each stake in `0.99`, `1.00`, `100.00`, `100.01`, `1.005`, `-1`, `"ten"`,
send `POST /api/place-bet` directly with a valid `matchId`, `selection: HOME`
and a valid `x-user-id`, reading `GET /api/balance` before and after.

**Expected result**
- `1.00` and `100.00` are accepted (HTTP 200).
- `0.99`, `100.01`, `1.005`, `-1` and `"ten"` are rejected with HTTP 422 (or
  400 for the non-numeric case), never a 5xx.
- The balance is byte-identical before and after every rejected request.

**Evidence (executed 2026-09-03)** The API-level matrix is automated (see
`tests/api/test_place_bet.py`); the equivalent UI-side boundary, driven
manually for this evidence, matches the documented copy in both directions:
[`docs/screenshots/03_stake_below_minimum.png`](screenshots/03_stake_below_minimum.png)
("Minimum stake is €1.00") and
[`04_stake_above_maximum.png`](screenshots/04_stake_above_maximum.png)
("Maximum stake is €100.00"), both with Place Bet correctly disabled.

---

### TP-03 — A stake above the available balance is refused and no money moves
**Priority:** Critical
**Risk rationale:** The only rule that lets a customer go into negative funds.
It is also the rule most likely to break under a partially applied change,
because it depends on live state rather than a constant. Note the ceiling
(€100) sits below the opening balance (€125.50), so this state is only
reachable after prior spend — exactly the kind of setup an untested path hides in.

**Steps**
1. Reset the balance to €125.50.
2. Place a valid bet of €100.00 so €25.50 remains.
3. Attempt a further bet of €50.00, via the UI and via the API.

**Expected result**
- The UI shows "Insufficient balance" and keeps **Place Bet** unavailable.
- The API rejects with HTTP 422 and a message naming the balance.
- The balance stays at €25.50 in the header, the slip and `GET /api/balance`.

**Evidence (executed 2026-09-03)** The API side is confirmed - see
`test_a_stake_above_the_remaining_balance_is_refused`, `xfail`ed for BUG-015
(a stake above the balance is accepted, not rejected). The UI side could not
be cleanly captured as a standalone screenshot: BUG-021 (balance does not
refresh after a bet) means the setup bet's deduction never becomes visible in
the UI without a reload, so the "Insufficient balance" step is exercised
against a stale, higher balance every time - see
[`07_balance_after_closing_receipt.png`](screenshots/07_balance_after_closing_receipt.png)
for the underlying cause.

---

### TP-04 — Selecting a new outcome replaces the previous selection
**Priority:** High
**Risk rationale:** Section 2.2 permits exactly one active selection. If a second
selection is *added* rather than *substituted*, the punter can be shown one bet
and charged for another — a mis-selling risk with a trivial reproduction.

**Steps**
1. Select `1` on match A; confirm the slip shows it.
2. Select `2` on the same match.
3. Select `1` on match B.

**Expected result** After each click the slip holds exactly one selection — the
most recent one — and only one odds button is rendered as active on the page.

---

### TP-05 — Placement always resolves, and a failure clears down cleanly
**Priority:** High
**Risk rationale:** Section 2.3 requires the in-progress state to reach exactly
one final outcome. A slip stuck on `Placing...` is the worst possible state: the
punter does not know whether their money is committed, and support cannot tell
them. The error modal's two exits have deliberately *different* semantics
(**Rebet** retries, **Close** and **X** discard), which is a classic place for
them to be wired identically.

**Steps**
1. Drive placement until the failure path appears (retry, or force it with a
   throttled/offline network profile in devtools).
2. Confirm the modal title and body copy.
3. Press **Rebet** and observe.
4. Repeat and exit with **Close**, then again with the top-right **X**.

**Expected result**
- The button never remains in `Placing...` indefinitely.
- The modal reads "Something went wrong" and offers both actions.
- **Rebet** closes the modal and retries the same bet.
- **Close** and **X** behave identically: modal closes, selection and stake cleared.
- No balance movement on any failed attempt.

---

### TP-06 — An invalid odds filter range is rejected with clear feedback
**Priority:** Medium
**Risk rationale:** Lower blast radius — no money moves — but section 2.6
explicitly requires *clear feedback* on an invalid range. The failure mode worth
catching is the silent one: an empty match list that looks like "no fixtures
today" instead of "your filter is impossible", which quietly costs turnover.

**Steps**
1. Set the odds filter minimum to `5.00` and the maximum to `1.50`.
2. Apply, and observe the list and any message.
3. Repeat with an inverted date range.
4. Set an inclusive valid range (`1.01`–`1000.00`) and confirm results return.

**Expected result** An explicit validation message identifies the range as
invalid; the catalogue is not silently emptied. Valid ranges are inclusive of
both bounds.

---

## Automation mapping

Every test's docstring opens with its `TC_` identifier, so a report traces back
to this plan.

| Plan ID | Automated as | Suite |
|---------|--------------|-------|
| TP-01 | `tests/ui/test_place_bet_journey.py::test_place_a_bet_end_to_end_and_receive_a_consistent_receipt` (`TC_SBP_UI_001`) | smoke |
| TP-02 | `tests/api/test_place_bet.py` — the stake matrix, `TC_SBP_BET_B1`…`B7` | smoke + regression |
| TP-03 | `tests/api/test_place_bet.py::test_a_stake_above_the_remaining_balance_is_refused` (`TC_SBP_BET_B8`) and `tests/ui/test_stake_validation.py::test_a_stake_larger_than_the_balance_is_refused` (`TC_SBP_UI_V5`) | regression |
| TP-04 | `tests/ui/test_place_bet_journey.py` — `TC_SBP_UI_003`, `TC_SBP_UI_004` | regression |
| TP-05 | Manual — the failure path cannot be triggered deterministically. See `03_strategy_and_recommendations.md`. | — |
| TP-06 | `tests/ui/test_filters.py` | regression |
