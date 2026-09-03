"""Thin wrapper over Allure so the rest of the code never imports it directly.

Two benefits: the suite still runs if Allure is not installed, and every payload
goes through `redact()` before it reaches a report.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from config.settings import SENSITIVE_KEY_FLOOR, get_settings, mask

try:  # pragma: no cover - reporting must never break a test run
    import allure
    from allure_commons.types import AttachmentType

    _ALLURE = True
except ImportError:  # pragma: no cover
    _ALLURE = False


def redact(value: Any) -> Any:
    """Replace user ids and any sensitive-looking key with a masked placeholder."""
    settings_user_ids: set[str] = set()
    # Redaction must survive an unreadable configuration: collection can run
    # before `USER_ID` is set, and secrets must stay masked even then.
    with contextlib.suppress(Exception):
        settings_user_ids = {get_settings().user_id} - {""}

    if isinstance(value, dict):
        return {k: ("<redacted>" if str(k).lower() in SENSITIVE_KEY_FLOOR else redact(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for user_id in settings_user_ids:
            if user_id and user_id in value:
                value = value.replace(user_id, mask(user_id))
        return value
    return value


def log(message: str, name: str = "Step") -> None:
    """Attach a plain-text note to the current Allure step (no-op without Allure)."""
    print(f"[{name}] {message}")
    if _ALLURE:
        allure.attach(message, name=name, attachment_type=AttachmentType.TEXT)


def attach_json(payload: Any, name: str) -> None:
    body = json.dumps(redact(payload), indent=2, ensure_ascii=False, default=str)
    print(f"[{name}]\n{body}")
    if _ALLURE:
        allure.attach(body, name=name, attachment_type=AttachmentType.JSON)


def attach_png(data: bytes, name: str) -> None:
    if _ALLURE:
        allure.attach(data, name=name, attachment_type=AttachmentType.PNG)
