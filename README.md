# Single Bet Placement — Test Automation

Automation for the *Single Bet Placement* feature: a Selenium + pytest browser
layer and a `requests` API layer, reported through Allure.

**Stack:** Python 3.12+ · pytest 9 · Selenium 4 · requests · jsonschema ·
Allure · pre-commit

---

## Quick start

```bash
make install
```

```bash
cp .env.example .env
```

Fill in `USER_ID` in `.env` — it is the only value you must provide.

```bash
make hooks
```

```bash
make smoke
```

Without `make`, the equivalent is `python3 -m venv .venv && .venv/bin/pip
install -r requirements-dev.txt`, then `.venv/bin/pytest -m smoke`.

## Running the suites

Everything runs through plain `pytest`; the suite you want is a marker.

```bash
pytest -m smoke
```

| Selector | What it runs |
|----------|--------------|
| `-m smoke` | 16 critical tests — the pull-request gate |
| `-m regression` | 136 tests — the full validation matrix |
| `-m api` | 132 API tests, no browser needed |
| `-m ui` | 20 browser tests |
| *(no marker)* | All 152 |

Markers compose (`pytest -m "smoke and api"`, `pytest -m "regression and not
slow"`) and select by test name (`pytest -k "minimum_stake"`). The `Makefile`
wraps the same commands as a shortcut only — nothing depends on it.

Declared markers: `smoke`, `regression`, `api`, `ui`, `e2e`, `boundary`,
`negative`, `security`, `spec_gap`, `concurrency`, `slow`. `--strict-markers` is
on, so a misspelled marker fails the run instead of silently matching nothing.
Each test's docstring opens with its test-plan id (`TC_SBP_BET_B1`), tracing
back to `docs/01_test_plan.md`.

## Reports

Allure results are written to `reports/allure-results` on every run.

```bash
make report
```

Install Allure itself with `brew install allure` (or see the
[Allure install guide](https://allurereport.org/docs/install/)). Each API call
attaches its request and response; each UI failure attaches a screenshot and the
severe browser console errors. Secrets are masked on the way in — see
`tests/support/reporting.py`.

## Configuration and secrets

No credential is ever committed. Everything comes from the environment:
`.env` for local runs (git-ignored), repository secrets in CI.

| Variable | Required | Purpose |
|----------|----------|---------|
| `BASE_URL` / `API_BASE_URL` | **yes** | The environment under test |
| `USER_ID` | **yes** (secret) | Sent as `x-user-id` (API) and `?user-id=` (UI) |
| `UNKNOWN_USER_ID` | **yes** | An unprovisioned id for the user-isolation test |
| `INITIAL_BALANCE`, `CURRENCY`, `STAKE_MIN`, `STAKE_MAX`, `STAKE_DECIMALS`, `ODDS_MIN`, `ODDS_MAX` | **yes** | Business rules from spec §3 |
| `HEADLESS`, `BROWSER`, `WINDOW_WIDTH`, `WINDOW_HEIGHT` | no | How the browser is driven |
| `EXPLICIT_WAIT`, `PAGE_LOAD_TIMEOUT` | no | Browser timeouts |
| `BROWSER_LOG_LEVEL`, `BROWSER_LANGUAGES` | no | Console capture level and the locale pinned for the browser |

The required ones have **no fallback in code** — a run against the wrong
`STAKE_MAX` would silently pass and mean nothing, so a missing or unparseable
value fails immediately and names the variable. `.env.example` already carries
every non-secret required value, so `cp .env.example .env` plus your `USER_ID`
is a complete setup. `config/settings.py` is the only place that reads the
environment.

Three layers keep secrets out of the repository: `.gitignore`, a
`detect-secrets` pre-commit hook, and a hook that refuses a `.env` outright.

## Project layout

```
config/                      Settings, endpoint catalogue, JSON schemas
  settings.py                Env-driven config; USER_ID is required and masked in logs
  schemas/                   Response contracts asserted per endpoint

tests/
  conftest.py                Fixtures: api, app, clean_balance, match, evidence capture
  api/                       test_get_matches, test_get_balance,
                             test_place_bet, test_reset_balance
  ui/                        test_place_bet_journey, test_stake_validation, test_filters
  app_actions/               The App Actions layer
    api/                     http_client.py (request shaping) + betting_api_actions.py
    ui/                      driver_factory, base_actions, locators
      components/            One class per screen region: match_list, bet_slip,
                             receipt, error_modal, filters
      betting_app_actions.py Facade composing the components
  support/
    payloads.py              Hostile inputs, boundary values, request-body builder
    api_assertions.py        Response-level assertions with diagnosable messages
    assertions.py            Money and schema helpers
    reporting.py             Allure attachments, with secrets redacted

docs/                        Test plan, execution & bugs, strategy
scripts/                     Repository health checks used by pre-commit
```

### The App Actions pattern

Tests express **business intent**, not mechanics — `app.place_bet_and_wait()`
owns its own waiting and returns `"success"`/`"failure"`; a test never touches
a locator or a `WebDriverWait`:

```python
page.matches.select_odds("HOME")
page.slip.enter_stake("10.00")
page.place_bet_and_wait()          # spans slip -> receipt or error modal
receipt = page.receipt.read()
```

`BettingAppActions` is a thin facade over `components/` (one class per screen
region); it keeps only the flows that genuinely cross components. UI tests
arrange their data through the API App Actions rather than the browser, since
that's faster and tests the right thing.

**Locators:** `tests/app_actions/ui/locators.py` is the only file that knows
about the DOM — real selectors, verified against the running application (the
app ships no `data-testid` at all, only plain `id`s discovered by inspection).

### Test data

Hostile inputs and boundary values live in `tests/support/payloads.py` as plain
Python and feed `@pytest.mark.parametrize` directly, so a new class of hostile
input reaches every negative test via one dictionary entry. `MISSING` is a
sentinel `bet_body()` uses to omit a field entirely, keeping "absent" and
"null" distinct assertions.

## Code quality

`make check` (`make lint` for formatting only) runs black, isort, ruff,
`detect-secrets`, a `.env` guard, and `scripts/check_test_markers.py` - two
`pytest --collect-only` runs proving no test is marked with neither `smoke` nor
`regression` (CI's two gates) nor both, and that every module still imports.

CI mirrors this: lint, then smoke on every pull request, full regression
nightly, serialised through a concurrency group since the suite mutates one
shared balance per user id.

## Tooling choices

- **Plain pytest, not Gherkin** — parametrisation and markers already express a
  validation matrix; test data as typed Python fails an import instead of
  silently mismatching a table.
- **Allure over pytest-html** — request/response and screenshot attachments make
  a failure diagnosable from the report alone.
- **jsonschema over hand-written assertions** — contracts live in
  `config/schemas/` as data, so a shape change produces one clear diff.
- **Decimal, never float, for money** — `0.1 + 0.2 != 0.3`, and payouts must be
  exact.
- **`requirements.txt` over Poetry** — fewer moving parts for a dependency graph
  this small.

## Verification status

Executed against the real, deployed application (2026-09-03), not only a local
mock: API **132/132** (119 passed, 13 xfailed) on two separate full runs; every
UI fix individually confirmed live. `locators.py` was rewritten from the real
DOM - the app ships no `data-testid` at all.

That run surfaced **25 real, reproduced defects** - 10 from cross-reading the
spec documents before the app opened, 15 only reachable by executing (full
reproduction and business impact in `docs/02_execution_and_bug_reports.md`).
Every affected test is marked `@pytest.mark.xfail` with the bug id, so the
suite stays green and self-documenting: a fix landing on the real app flips
that test to an unexpected pass, the signal to remove the marker.

Two passes got it here, each catching what the other couldn't: a local mock
(stub API + mock page) proved the framework's wiring before the real app was
reachable; the real application then caught what only real markup and real
data could - a fallback locator that silently resolves to *something* is more
dangerous than one that fails loudly, because the wrong-but-plausible answer
is the one that doesn't get double-checked.

## Deliverables

| Document | Contents |
|----------|----------|
| [`docs/01_test_plan.md`](docs/01_test_plan.md) | Six prioritised scenarios with risk rationale |
| [`docs/02_execution_and_bug_reports.md`](docs/02_execution_and_bug_reports.md) | Execution notes and defect reports |
| [`docs/03_strategy_and_recommendations.md`](docs/03_strategy_and_recommendations.md) | Automation rationale and scaling recommendations |

## Troubleshooting

**`MissingSettingError: Required environment variable 'USER_ID' is not set`** —
copy `.env.example` to `.env` and fill in `USER_ID`.

**`ElementNotFoundError: None of the candidate locators resolved`** — the
application markup differs from the assumption. The message names the candidates
it tried; update `tests/app_actions/ui/locators.py`.

**Chrome fails to start** — Selenium 4.25 resolves the driver automatically via
Selenium Manager; make sure desktop Chrome is installed and on a recent version.

**Balance-dependent tests fail in sequence** — the suite resets the balance
around each test that spends, but two runs sharing one `USER_ID` will collide.
Do not run two suites against the same identity at once.
