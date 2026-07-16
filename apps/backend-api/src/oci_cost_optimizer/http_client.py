from __future__ import annotations

import json
from http.client import RemoteDisconnected
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ServiceCallError(RuntimeError):
    pass


def get_json(url: str, query: dict[str, str] | None = None, *, timeout: float = 3.0) -> dict[str, Any]:
    target = f"{url}?{urlencode(query or {})}" if query else url
    request = Request(target, headers={"accept": "application/json"})
    return _read_json(request, timeout=timeout)


def post_json(url: str, payload: dict[str, Any], *, timeout: float = 8.0) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={"content-type": "application/json", "accept": "application/json"},
    )
    return _read_json(request, timeout=timeout)


def _read_json(request: Request, *, timeout: float) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, RemoteDisconnected, json.JSONDecodeError) as error:
        raise ServiceCallError(str(error)) from error

    if not isinstance(payload, dict):
        raise ServiceCallError("Service returned a non-object JSON payload.")

    return payload
