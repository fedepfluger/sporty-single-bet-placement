"""Central, read-only configuration.

Every value comes from the process environment; `.env` supplies it for local runs
and repository secrets or variables do so in CI.

Anything that can differ between environments - the URLs, the account ids, the
monetary limits of the platform - is `_required`, with no fallback written here.
A default in code is a value that silently survives a misconfigured environment,
and for a suite that asserts money rules that means passing against the wrong
numbers. Only operational knobs (window size, timeouts, log level) keep defaults,
because they change how we drive the system, not what the system is.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "config" / "schemas"


def _load_env_file() -> None:
    """Load `.env`, letting it fill any variable the environment left empty.

    A CI runner exports an unset repository variable as an empty string, and
    `load_dotenv` treats that as "already set" and refuses to fill it. Clearing
    those keys first makes an empty override behave like an absent one, which
    matters now that the URLs and the monetary limits have no fallback in code.
    """
    env_file = PROJECT_ROOT / ".env"
    for key in dotenv_values(env_file):
        if key in os.environ and not os.environ[key].strip():
            del os.environ[key]
    load_dotenv(env_file, override=False)


_load_env_file()


#: Header and field names that must never reach a log or an Allure attachment.
SENSITIVE_KEY_FLOOR = frozenset({"x-user-id", "user-id", "userid", "authorization", "token", "password", "api-key"})


class MissingSettingError(RuntimeError):
    """Raised when a required setting is absent from the environment."""


def _required(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise MissingSettingError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill it in, or export it in your CI secrets."
        )
    return value


def _optional(key: str, default: str) -> str:
    value = os.getenv(key, "").strip()
    return value or default


def _bool(key: str, default: bool) -> bool:
    return _optional(key, str(default)).lower() in {"1", "true", "yes", "on"}


def _int(key: str, default: int) -> int:
    return int(_optional(key, str(default)))


def _required_int(key: str) -> int:
    return _parsed(key, _required(key), int)


def _required_decimal(key: str) -> Decimal:
    return _parsed(key, _required(key), Decimal)


def _parsed(key: str, raw: str, kind: Callable[[str], Any]) -> Any:
    """Convert a required value, naming the variable when the value is unusable."""
    try:
        return kind(raw)
    except (ArithmeticError, ValueError) as exc:
        raise MissingSettingError(f"Environment variable '{key}' has an invalid value: {raw!r}") from exc


def mask(secret: str) -> str:
    """Render a secret safe for logs and reports: only the last 4 characters survive."""
    if not secret:
        return "<empty>"
    return f"{'*' * max(len(secret) - 4, 3)}{secret[-4:]}"


@dataclass(frozen=True)
class BusinessRules:
    """Business rules from the Feature Specification, section 3."""

    initial_balance: Decimal
    currency: str
    stake_min: Decimal
    stake_max: Decimal
    stake_decimals: int
    odds_min: Decimal
    odds_max: Decimal


@dataclass(frozen=True)
class BrowserSettings:
    name: str
    headless: bool
    width: int
    height: int
    explicit_wait: int
    page_load_timeout: int
    log_level: str
    languages: str


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_base_url: str
    user_id: str
    unknown_user_id: str
    browser: BrowserSettings
    rules: BusinessRules

    def ui_url(self, user_id: str | None = None) -> str:
        """UI entry point with the authenticating `user-id` query parameter."""
        return f"{self.base_url}/?user-id={user_id or self.user_id}"

    def endpoint(self, path: str) -> str:
        return f"{self.api_base_url}/{path.lstrip('/')}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        base_url=_required("BASE_URL").rstrip("/"),
        api_base_url=_required("API_BASE_URL").rstrip("/"),
        user_id=_required("USER_ID"),
        unknown_user_id=_required("UNKNOWN_USER_ID"),
        browser=BrowserSettings(
            name=_optional("BROWSER", "chrome").lower(),
            headless=_bool("HEADLESS", True),
            width=_int("WINDOW_WIDTH", 1440),
            height=_int("WINDOW_HEIGHT", 900),
            explicit_wait=_int("EXPLICIT_WAIT", 15),
            page_load_timeout=_int("PAGE_LOAD_TIMEOUT", 30),
            log_level=_optional("BROWSER_LOG_LEVEL", "SEVERE").upper(),
            languages=_optional("BROWSER_LANGUAGES", "en-GB,en"),
        ),
        rules=BusinessRules(
            initial_balance=_required_decimal("INITIAL_BALANCE"),
            currency=_required("CURRENCY"),
            stake_min=_required_decimal("STAKE_MIN"),
            stake_max=_required_decimal("STAKE_MAX"),
            stake_decimals=_required_int("STAKE_DECIMALS"),
            odds_min=_required_decimal("ODDS_MIN"),
            odds_max=_required_decimal("ODDS_MAX"),
        ),
    )
