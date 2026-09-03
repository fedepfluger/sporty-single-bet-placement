"""A single, well-behaved HTTP client for the betting API.

Everything the tests send goes through here, which is what makes the negative
matrix cheap to write: a scenario only says *what* is wrong with the request
(missing header, malformed body, wrong verb) and the client keeps the rest valid.
"""

from __future__ import annotations

from typing import Any

import requests

from config.settings import get_settings
from tests.support.reporting import attach_json, log

#: Sentinel meaning "do not send this header at all", as opposed to sending it empty.
OMIT = object()


class ApiClient:
    def __init__(self, user_id: str | None = None) -> None:
        self._settings = get_settings()
        self._session = requests.Session()
        self._user_id = self._settings.user_id if user_id is None else user_id
        self._extra_headers: dict[str, Any] = {}

    # --- request shaping -------------------------------------------------
    def with_user_id(self, user_id: str | None | object) -> ApiClient:
        """Override the auth context. Pass `OMIT` to drop the header entirely."""
        self._user_id = user_id
        return self

    def with_headers(self, headers: dict[str, Any]) -> ApiClient:
        self._extra_headers.update(headers)
        return self

    def build_headers(self, content_type: str | None = "application/json") -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if self._user_id is not OMIT:
            # Feature Specification 5.1: the API expects the user context on this header.
            headers["x-user-id"] = "" if self._user_id is None else str(self._user_id)
        headers.update({k: "" if v is None else str(v) for k, v in self._extra_headers.items()})
        return headers

    # --- verbs -----------------------------------------------------------
    def get(self, path: str, params: dict[str, Any] | None = None) -> requests.Response:
        return self.request("GET", path, params=params)

    def post(self, path: str, json_body: Any = None, params: dict[str, Any] | None = None) -> requests.Response:
        return self.request("POST", path, json_body=json_body, params=params)

    def request(
        self,
        method: str,
        path: str,
        json_body: Any = None,
        raw_body: str | bytes | None = None,
        params: dict[str, Any] | None = None,
        content_type: str | None = "application/json",
    ) -> requests.Response:
        url = self._settings.endpoint(path)
        headers = self.build_headers(content_type)
        log(f"{method} {url} params={params}", name="API request")
        if json_body is not None:
            attach_json(json_body, name="Request body")
        if raw_body is not None:
            log(f"Raw body: {raw_body!r}", name="Request body (raw)")

        response = self._session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body if raw_body is None else None,
            data=raw_body,
            timeout=20,  # seconds; a hung API must not hang the whole suite
        )
        self._report(response)
        return response

    @staticmethod
    def _report(response: requests.Response) -> None:
        log(f"HTTP {response.status_code} in {response.elapsed.total_seconds():.3f}s", name="API response")
        try:
            attach_json(response.json(), name="Response body")
        except ValueError:
            log(response.text[:2000] or "<empty body>", name="Response body (non-JSON)")

    def close(self) -> None:
        self._session.close()
