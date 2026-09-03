"""Fixtures shared by the API and UI tests."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from config.settings import Settings, get_settings
from tests.app_actions.api.betting_api_actions import BettingApiActions
from tests.app_actions.api.http_client import ApiClient
from tests.app_actions.ui.betting_app_actions import BettingAppActions
from tests.app_actions.ui.driver_factory import create_driver
from tests.support.reporting import attach_png, log


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def api_client(settings: Settings) -> Iterator[ApiClient]:
    client = ApiClient()
    yield client
    client.close()


@pytest.fixture
def api(api_client: ApiClient) -> BettingApiActions:
    """App Actions for the betting API - the entry point for every API test."""
    return BettingApiActions(api_client)


@pytest.fixture
def clean_balance(api: BettingApiActions) -> Iterator[BettingApiActions]:
    """Put the user on a known balance before and after a test.

    Balance is shared mutable state for a user id, so tests that spend money must
    not leave the next test guessing. Resetting on both sides keeps a failed run
    from poisoning the following one.
    """
    api.reset_balance_to_initial()
    yield api
    api.reset_balance_to_initial()


@pytest.fixture
def match(api: BettingApiActions) -> dict[str, Any]:
    """A match from the live catalogue, so bets are placed against real data."""
    return api.first_match()


@pytest.fixture
def balance_before(api: BettingApiActions) -> Decimal:
    """The balance at the start of the test, for 'no money moved' assertions."""
    return api.read_balance()


@pytest.fixture
def driver() -> Iterator[Any]:
    web_driver = create_driver()
    yield web_driver
    web_driver.quit()


@pytest.fixture
def app(driver, clean_balance) -> BettingAppActions:
    """App Actions for the UI, on a browser whose user already has a clean balance."""
    return BettingAppActions(driver)


@pytest.fixture
def betting_page(app: BettingAppActions) -> BettingAppActions:
    """The betting page, loaded and rendered - the starting point of every UI test."""
    return app.open_betting_page()


@pytest.fixture(autouse=True)
def _attach_failure_evidence(request) -> Iterator[None]:
    """On failure, attach a screenshot and the severe console errors to Allure."""
    yield
    report = getattr(request.node, "rep_call", None)
    if report is None or not report.failed:
        return
    web_driver = request.node.funcargs.get("driver")
    if web_driver is None:
        return
    try:
        attach_png(web_driver.get_screenshot_as_png(), name="Screenshot on failure")
        errors = [e["message"] for e in web_driver.get_log("browser") if e.get("level") == "SEVERE"]
        if errors:
            log("\n".join(errors), name="Browser console errors")
    except Exception as exc:  # noqa: BLE001 - evidence capture must never mask the real failure
        log(f"Could not capture failure evidence: {exc}", name="Evidence")


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Expose each phase's report so fixtures can tell a failure from a pass."""
    outcome = yield
    setattr(item, f"rep_{call.when}", outcome.get_result())
