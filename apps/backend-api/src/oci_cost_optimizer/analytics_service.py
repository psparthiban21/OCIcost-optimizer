from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlparse

from .config import Settings, load_settings
from .data_provider import create_cost_optimizer_data
from .server import configure_logging, log_event


def _filters_from_query(query: str) -> dict[str, str]:
    params = parse_qs(query)
    return {
        "service": params.get("service", ["all"])[0],
        "region": params.get("region", ["all"])[0],
    }


class AnalyticsHandler(BaseHTTPRequestHandler):
    settings: Settings
    server_version = "OciCostOptimizerAnalytics/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        filters = _filters_from_query(parsed.query)

        if parsed.path in {"/health", "/internal/v1/health"}:
            self._send_json({"ok": True, "service": "analytics-engine", "mode": self.settings.mode})
            return

        if parsed.path in {"/ready", "/internal/v1/ready"}:
            self._send_json({"ready": True, "service": "analytics-engine", "dataProvider": self.settings.data_provider})
            return

        if parsed.path == "/internal/v1/dashboard":
            self._send_json(create_cost_optimizer_data(filters, self.settings))
            return

        if parsed.path == "/internal/v1/recommendations":
            data = create_cost_optimizer_data(filters, self.settings)
            self._send_json({"meta": data["meta"], "recommendations": data["recommendations"]})
            return

        self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        log_event("analytics_http_request", method=self.command, path=self.path, client=self.client_address[0], message=format % args)

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("x-content-type-options", "nosniff")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(settings: Settings | None = None) -> ThreadingHTTPServer:
    settings = settings or load_settings()

    class ConfiguredHandler(AnalyticsHandler):
        pass

    ConfiguredHandler.settings = settings
    return ThreadingHTTPServer((settings.host, settings.port), ConfiguredHandler)


def main() -> None:
    configure_logging()
    settings = load_settings()
    server = create_server(settings)
    log_event("analytics_service_started", url=f"http://{settings.host}:{settings.port}", mode=settings.mode)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log_event("analytics_service_stopping")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
