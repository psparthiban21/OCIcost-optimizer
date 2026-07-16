from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import metadata
import json
import logging
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from .config import Settings, load_settings, select_env_file
from .data_provider import answer_copilot, create_cost_optimizer_data
from .setup_status import create_setup_status


LOGGER = logging.getLogger("oci_cost_optimizer")
API_PREFIX = "/api/v1"
LEGACY_API_PREFIX = "/api"
MAX_JSON_BODY_BYTES = 64 * 1024


class BadRequestError(ValueError):
    pass


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


def _api_route(path: str) -> tuple[str | None, bool]:
    if path == API_PREFIX:
        return "/", False

    if path.startswith(f"{API_PREFIX}/"):
        return path.removeprefix(API_PREFIX), False

    if path == LEGACY_API_PREFIX:
        return "/", True

    if path.startswith(f"{LEGACY_API_PREFIX}/"):
        return path.removeprefix(LEGACY_API_PREFIX), True

    return None, False


def _service_version() -> str:
    try:
        return metadata.version("oci-cost-optimizer-backend")
    except metadata.PackageNotFoundError:
        return "0.1.0"


class ApiHandler(BaseHTTPRequestHandler):
    settings: Settings

    server_version = "OciCostOptimizerPython/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route, legacy_api = _api_route(parsed.path)
        filters = _filters_from_query(parsed.query)

        if route == "/health":
            self._send_json(self._health_payload(), legacy_api=legacy_api)
            return

        if route == "/ready":
            setup = create_setup_status(self.settings)
            self._send_json({**setup, "dependencies": self._dependencies_payload()}, legacy_api=legacy_api)
            return

        if route == "/version":
            self._send_json(self._version_payload(), legacy_api=legacy_api)
            return

        if route == "/status":
            setup = create_setup_status(self.settings)
            self._send_json(
                {
                    "service": self._version_payload(),
                    "health": self._health_payload(),
                    "ready": setup["ready"],
                    "dependencies": self._dependencies_payload(),
                    "setup": {
                        "dataProvider": setup["dataProvider"],
                        "missing": setup["missing"],
                    },
                },
                legacy_api=legacy_api,
            )
            return

        if route == "/setup":
            self._send_json(create_setup_status(self.settings), legacy_api=legacy_api)
            return

        if route == "/dashboard":
            self._send_json(create_cost_optimizer_data(filters, self.settings), legacy_api=legacy_api)
            return

        if route == "/recommendations":
            data = create_cost_optimizer_data(filters, self.settings)
            self._send_json({"meta": data["meta"], "recommendations": data["recommendations"]}, legacy_api=legacy_api)
            return

        if route is not None:
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND, legacy_api=legacy_api)
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route, legacy_api = _api_route(parsed.path)

        if route == "/setup/env-file":
            self._handle_env_file_setup(legacy_api=legacy_api)
            return

        if route != "/copilot":
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND, legacy_api=legacy_api)
            return

        try:
            body = self._read_json_body()
        except BadRequestError as error:
            self._send_json({"error": "invalid_request", "message": str(error)}, status=HTTPStatus.BAD_REQUEST, legacy_api=legacy_api)
            return

        answer = answer_copilot(body.get("question", ""), body.get("filters", {}), self.settings)
        self._send_json({"answer": answer, "mode": self.settings.mode}, legacy_api=legacy_api)

    def _handle_env_file_setup(self, *, legacy_api: bool = False) -> None:
        try:
            body = self._read_json_body()
        except BadRequestError as error:
            self._send_json({"error": "invalid_request", "message": str(error)}, status=HTTPStatus.BAD_REQUEST, legacy_api=legacy_api)
            return

        path = str(body.get("path", "")).strip()

        if not path:
            self._send_json({"error": "missing_env_file_path"}, status=HTTPStatus.BAD_REQUEST, legacy_api=legacy_api)
            return

        try:
            selected = select_env_file(path)
            type(self).settings = load_settings()
        except FileNotFoundError:
            self._send_json(
                {
                    "error": "env_file_not_found",
                    "message": "The file must exist at this path from inside the app or Docker container.",
                    "path": path,
                },
                status=HTTPStatus.BAD_REQUEST,
                legacy_api=legacy_api,
            )
            return

        setup = create_setup_status(self.settings)
        log_event("env_file_selected", path=str(selected), setup_ready=setup["ready"])
        self._send_json({"ok": True, "envFile": str(selected), "setup": setup}, legacy_api=legacy_api)

    def log_message(self, format: str, *args: object) -> None:
        log_event("http_request", method=self.command, path=self.path, client=self.client_address[0], message=format % args)

    def _read_json_body(self) -> dict[str, object]:
        content_length = int(self.headers.get("content-length", "0"))

        if content_length == 0:
            return {}

        if content_length > MAX_JSON_BODY_BYTES:
            raise BadRequestError("JSON body is too large.")

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise BadRequestError("Request body must be valid JSON.") from error

        if not isinstance(payload, dict):
            raise BadRequestError("Request body must be a JSON object.")

        return payload

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK, *, legacy_api: bool = False) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self._send_standard_headers()
        if legacy_api:
            self.send_header("deprecation", "true")
            self.send_header("link", f'<{API_PREFIX}>; rel="successor-version"')
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, requested_path: str) -> None:
        if requested_path == "/":
            relative_path = "index.html"
        elif requested_path == "/setup":
            relative_path = "setup.html"
        else:
            relative_path = requested_path.lstrip("/")
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
        self._send_standard_headers()
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_standard_headers(self) -> None:
        request_id = self.headers.get("x-request-id") or str(uuid4())
        self.send_header("x-request-id", request_id)
        self.send_header("x-content-type-options", "nosniff")
        self.send_header("referrer-policy", "no-referrer")
        self.send_header("x-frame-options", "DENY")

    def _health_payload(self) -> dict[str, object]:
        return {"ok": True, "mode": self.settings.mode, "service": self.settings.app_name}

    def _version_payload(self) -> dict[str, object]:
        return {
            "service": self.settings.app_name,
            "version": _service_version(),
            "apiVersion": "v1",
            "apiPrefix": API_PREFIX,
        }

    def _dependencies_payload(self) -> dict[str, str]:
        return {"database": "mock", "cache": "mock", "llm": self.settings.llm_provider}


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
