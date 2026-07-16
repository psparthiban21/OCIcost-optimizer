from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any

from .config import Settings, load_settings
from .data_provider import answer_copilot, create_cost_optimizer_data
from .oci_data import OciDataError
from .ollama_client import OllamaError, generate_with_ollama
from .server import BadRequestError, MAX_JSON_BODY_BYTES, configure_logging, log_event


class AgentHandler(BaseHTTPRequestHandler):
    settings: Settings
    server_version = "OciCostOptimizerAgent/0.1"

    def do_GET(self) -> None:
        if self.path in {"/health", "/internal/v1/health"}:
            self._send_json({"ok": True, "service": "agent-service", "llm": self.settings.llm_provider})
            return

        if self.path in {"/ready", "/internal/v1/ready"}:
            self._send_json({"ready": True, "service": "agent-service", "llm": self.settings.llm_provider})
            return

        self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path not in {"/internal/v1/copilot", "/internal/v1/predict", "/internal/v1/suggest"}:
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            body = self._read_json_body()
        except BadRequestError as error:
            self._send_json({"error": "invalid_request", "message": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return

        question = str(body.get("question", "")).strip()
        filters = body.get("filters", {})
        filters = filters if isinstance(filters, dict) else {}
        fallback = answer_copilot(question, filters, self.settings)

        if self.settings.llm_provider == "ollama":
            prompt = self._build_prompt(question, filters, fallback)
            try:
                answer = generate_with_ollama(prompt, self.settings)
                self._send_json({"answer": answer, "provider": "ollama", "model": self.settings.ollama_model})
                return
            except OllamaError as error:
                log_event("ollama_fallback", reason=str(error))

        self._send_json({"answer": fallback, "provider": "mock-fallback", "model": self.settings.llm_provider})

    def log_message(self, format: str, *args: object) -> None:
        log_event("agent_http_request", method=self.command, path=self.path, client=self.client_address[0], message=format % args)

    def _build_prompt(self, question: str, filters: dict[str, Any], fallback: str) -> str:
        connection_status = "OCI live data is available."
        try:
            data = create_cost_optimizer_data(filters, self.settings)
        except OciDataError as error:
            connection_status = f"OCI live data is NOT currently available. Provider error: {error}"
            data = {
                "summary": {
                    "currentRunRate": 0,
                    "projectedNextMonth": 0,
                    "identifiedSavings": 0,
                    "openRecommendations": 1,
                },
                "recommendations": [
                    {
                        "severity": "high",
                        "service": "Billing",
                        "title": "OCI live provider is unavailable",
                        "evidence": str(error),
                        "action": "Verify the local OCI CLI can start and the configured read-only OCI profile has access.",
                    }
                ],
            }
        summary = data["summary"]
        recommendations = data["recommendations"][:5]
        return (
            "You are an OCI FinOps assistant. Use only the provided cost data. "
            "Do not claim that resources were changed. Do not recommend automatic deletion. "
            "Follow the connection status exactly; do not say connected when the status says not available. "
            "Keep the answer under 180 words and include practical next steps.\n\n"
            f"Connection status: {connection_status}\n"
            f"Question: {question}\n"
            f"Summary: current_run_rate={summary['currentRunRate']}, projected_next_month={summary['projectedNextMonth']}, "
            f"identified_savings={summary['identifiedSavings']}, open_recommendations={summary['openRecommendations']}.\n"
            f"Top recommendations: {json.dumps(recommendations, separators=(',', ':'))}\n"
            f"Deterministic fallback answer: {fallback}"
        )

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

    class ConfiguredHandler(AgentHandler):
        pass

    ConfiguredHandler.settings = settings
    return ThreadingHTTPServer((settings.host, settings.port), ConfiguredHandler)


def main() -> None:
    configure_logging()
    settings = load_settings()
    server = create_server(settings)
    log_event(
        "agent_service_started",
        url=f"http://{settings.host}:{settings.port}",
        llm_provider=settings.llm_provider,
        ollama_model=settings.ollama_model,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log_event("agent_service_stopping")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
