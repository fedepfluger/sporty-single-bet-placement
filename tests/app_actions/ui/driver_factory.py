"""WebDriver construction, isolated from the tests that use it.

Every option below is here because something breaks or drifts without it. Flags
that are folklore on other projects - `--disable-gpu`, `--no-sandbox`,
`--disable-dev-shm-usage`, `--incognito` - were measured against this suite and
removed: modern headless Chrome does not need them, and `--no-sandbox` in
particular switches off a real security boundary to solve a problem we do not
have (running as root inside a container).
"""

from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.remote.webdriver import WebDriver

from config.settings import BrowserSettings, get_settings


def _chrome_options(browser: BrowserSettings) -> ChromeOptions:
    options = ChromeOptions()
    if browser.headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={browser.width},{browser.height}")
    options.add_argument("--disable-search-engine-choice-screen")
    options.add_experimental_option("prefs", {"intl.accept_languages": browser.languages})
    options.set_capability("goog:loggingPrefs", {"browser": browser.log_level})
    return options


def create_driver() -> WebDriver:
    settings = get_settings()
    browser = settings.browser
    if browser.name != "chrome":
        raise ValueError(
            f"BROWSER='{browser.name}' is not supported. The assignment targets desktop Chrome; "
            f"add a factory branch here to widen coverage."
        )
    driver = webdriver.Chrome(options=_chrome_options(browser))
    driver.set_page_load_timeout(browser.page_load_timeout)
    return driver
