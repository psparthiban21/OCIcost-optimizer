from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import Settings, load_settings
from .data_provider import answer_copilot, create_cost_optimizer_data
from .setup_status import create_setup_status


LOGGER = logging.getLogger("oci_cost_optimizer")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(event: str, **fields: object) -> None:
    LOGGER.info(json.dumps({"event": event, **fields}, separators=(",", ":")))


def _filters_from_query(query: str) -> dict[str, str]:
    params = parse_qs(query)
    return {
        "service": params.get("service", ["all"])[0],
        "region": params.get("region", ["all"])[0],
    }


class ApiHandler(BaseHTTPRequestHandler):
    settings: Settings

    server_version = "OciCostOptimizerPython/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        filters = _filters_from_query(parsed.query)

        if parsed.path == "/api/health":
            self._send_json({"ok": True, "mode": self.settings.mode, "service": self.settings.app_name})
            return

        if parsed.path == "/api/ready":
            setup = create_setup_status(self.settings)
            self._send_json({**setup, "dependencies": {"database": "mock", "cache": "mock", "llm": "mock"}})
            return

        if parsed.path == "/api/setup":
            self._send_json(create_setup_status(self.settings))
            return

        if parsed.path == "/api/dashboard":
            self._send_json(create_cost_optimizer_data(filters, self.settings))
            return

        if parsed.path == "/api/recommendations":
            data = create_cost_optimizer_data(filters, self.settings)
            self._send_json({"meta": data["meta"], "recommendations": data["recommendations"]})
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/api/copilot":
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            return

        body = self._read_json_body()
        answer = answer_copilot(body.get("question", ""), body.get("filters", {}), self.settings)
        self._send_json({"answer": answer, "mode": self.settings.mode})

    def log_message(self, format: str, *args: object) -> None:
        log_event("http_request", method=self.command, path=self.path, client=self.client_address[0], message=format % args)

    def _read_json_body(self) -> dict[str, object]:
        content_length = int(self.headers.get("content-length", "0"))

        if content_length == 0:
            return {}

        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, requested_path: str) -> None:
        relative_path = "index.html" if requested_path == "/" else requested_path.lstrip("/")
        static_root = self.settings.static_root.resolve()
        file_path = (static_root / relative_path).resolve()

        if not file_path.is_relative_to(static_root) or not file_path.is_file():
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            return

        content_type = guess_type(file_path.name)[0] or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(settings: Settings | None = None) -> ThreadingHTTPServer:
    settings = settings or load_settings()

    class ConfiguredHandler(ApiHandler):
        pass

    ConfiguredHandler.settings = settings
    return ThreadingHTTPServer((settings.host, settings.port), ConfiguredHandler)


def main() -> None:
    configure_logging()
    settings = load_settings()
    server = create_server(settings)
    setup = create_setup_status(settings)
    log_event(
        "server_started",
        url=f"http://{settings.host}:{settings.port}",
        mode=settings.mode,
        data_provider=settings.data_provider,
        setup_ready=setup["ready"],
        static_root=str(settings.static_root),
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log_event("server_stopping")
    finally:
        server.server_close()
