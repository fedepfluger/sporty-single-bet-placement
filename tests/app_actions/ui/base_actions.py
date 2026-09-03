"""Shared Selenium mechanics for every UI App Action.

The cascading-locator resolution lives here: `find` walks the candidate list from
`locators.py` and returns the first element that actually exists, so a missing
`data-testid` degrades to a semantic fallback instead of failing the test.
"""

from __future__ import annotations

from typing import Any

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import get_settings
from tests.support.reporting import log

Candidates = list[tuple[str, str]]


class ElementNotFoundError(AssertionError):
    """Raised when none of an element's candidate locators resolves."""


class BaseActions:
    def __init__(self, driver: WebDriver) -> None:
        self.driver = driver
        self.settings = get_settings()
        self.timeout = self.settings.browser.explicit_wait

    # --- resolution ------------------------------------------------------
    def find(
        self, candidates: Candidates, context: WebElement | None = None, required: bool = True
    ) -> WebElement | None:
        scope: Any = context or self.driver
        for by, value in candidates:
            try:
                element = scope.find_element(by, value)
                # Visibility is part of "found": a modal that exists in the DOM but
                # is still hidden must not count as present, or every wait that
                # polls `is_present` resolves instantly against markup nobody sees.
                # `required` only decides whether absence raises or returns None.
                if element.is_displayed():
                    return element
            except (NoSuchElementException, StaleElementReferenceException):
                continue
        if required:
            raise ElementNotFoundError(
                f"None of the candidate locators resolved to a visible element: {candidates}. "
                f"If the application markup changed, update tests/app_actions/ui/locators.py."
            )
        return None

    def find_all(self, candidates: Candidates, context: WebElement | None = None) -> list[WebElement]:
        scope: Any = context or self.driver
        for by, value in candidates:
            elements = [e for e in scope.find_elements(by, value) if e.is_displayed()]
            if elements:
                return elements
        return []

    # --- waits -----------------------------------------------------------
    def wait(self, timeout: int | None = None) -> WebDriverWait:
        return WebDriverWait(
            self.driver,
            timeout or self.timeout,
            poll_frequency=0.2,
            ignored_exceptions=(StaleElementReferenceException,),
        )

    def wait_until(self, condition, timeout: int | None = None, message: str = "") -> Any:
        try:
            return self.wait(timeout).until(condition, message)
        except TimeoutException as exc:
            raise AssertionError(message or f"Condition not met within {timeout or self.timeout}s") from exc

    def wait_for_visible(self, candidates: Candidates, timeout: int | None = None) -> WebElement:
        return self.wait_until(
            lambda _: self.find(candidates, required=False),
            timeout=timeout,
            message=f"No element became visible for {candidates}",
        )

    def wait_for_absent(self, candidates: Candidates, timeout: int | None = None) -> None:
        self.wait_until(
            lambda _: self.find(candidates, required=False) is None,
            timeout=timeout,
            message=f"Element was still present: {candidates}",
        )

    def is_present(self, candidates: Candidates, context: WebElement | None = None) -> bool:
        return self.find(candidates, context=context, required=False) is not None

    # --- interaction -----------------------------------------------------
    def click(self, element: WebElement | Candidates, context: WebElement | None = None) -> WebElement:
        target = element if isinstance(element, WebElement) else self.find(element, context=context)
        self.scroll_into_view(target)
        self.wait_until(ec.element_to_be_clickable(target), message=f"Element never became clickable: {target}")
        try:
            target.click()
        except ElementClickInterceptedException:
            # Sticky headers and modal overlays are a common interceptor; the JS
            # click is a deliberate, logged fallback rather than a silent default.
            log("Native click intercepted, falling back to a JavaScript click", name="UI action")
            self.driver.execute_script("arguments[0].click();", target)
        return target

    def type_text(self, candidates: Candidates, text: str, clear: bool = True) -> WebElement:
        element = self.find(candidates)
        if clear:
            element.clear()
            # React-controlled inputs sometimes ignore `clear()`; select-all + delete is reliable.
            element.send_keys(Keys.CONTROL, "a")
            element.send_keys(Keys.COMMAND, "a")
            element.send_keys(Keys.DELETE)
        element.send_keys(text)
        return element

    def scroll_into_view(self, element: WebElement) -> None:
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", element)

    # --- reads -----------------------------------------------------------
    def text_of(self, candidates: Candidates, context: WebElement | None = None, default: str = "") -> str:
        element = self.find(candidates, context=context, required=False)
        return element.text.strip() if element else default

    def value_of(self, candidates: Candidates, context: WebElement | None = None) -> str:
        element = self.find(candidates, context=context)
        return element.get_attribute("value") or ""
