from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings


class OllamaError(RuntimeError):
    pass


def generate_with_ollama(prompt: str, settings: Settings, *, timeout: float = 20.0) -> str:
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 220,
            "temperature": 0.2,
        },
    }
    request = Request(
        f"{settings.ollama_base_url}/api/generate",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={"content-type": "application/json", "accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise OllamaError(str(error)) from error

    text = str(body.get("response", "")).strip()
    if not text:
        raise OllamaError("Ollama returned an empty response.")

    return text

