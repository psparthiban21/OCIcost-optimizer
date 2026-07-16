from __future__ import annotations

from email.message import Message
from io import BytesIO
from pathlib import Path
import unittest

from oci_cost_optimizer.config import Settings
from oci_cost_optimizer.server import ApiHandler, BadRequestError, _api_route


def _test_settings() -> Settings:
    return Settings(
        app_name="oci-cost-optimizer-backend",
        mode="mock",
        data_provider="mock",
        host="127.0.0.1",
        port=0,
        static_root=Path("."),
        project_root=Path("."),
        oci_cli_path=Path("oci"),
        oci_config_file=Path("missing-config"),
        oci_profile="DEFAULT",
        oci_tenancy_ocid="",
        oci_region="",
        oci_user_ocid="",
        oci_fingerprint="",
        oci_key_file=Path(""),
        llm_provider="mock",
        openai_api_key_set=False,
        openai_model="gpt-4.1-mini",
        env_file_path=Path(".env"),
        env_file_loaded=False,
    )


def _handler() -> ApiHandler:
    handler = object.__new__(ApiHandler)
    handler.settings = _test_settings()
    handler.headers = Message()
    handler.sent_headers = []
    handler.send_header = lambda key, value: handler.sent_headers.append((key, value))  # type: ignore[method-assign]
    return handler


class ServerApiTest(unittest.TestCase):
    def test_api_route_prefers_v1_and_marks_legacy_routes(self) -> None:
        self.assertEqual(_api_route("/api/v1/health"), ("/health", False))
        self.assertEqual(_api_route("/api/v1/dashboard"), ("/dashboard", False))
        self.assertEqual(_api_route("/api/health"), ("/health", True))
        self.assertEqual(_api_route("/api/dashboard"), ("/dashboard", True))
        self.assertEqual(_api_route("/dashboard"), (None, False))

    def test_standard_headers_are_enterprise_safe(self) -> None:
        handler = _handler()
        handler.headers["x-request-id"] = "request-123"

        handler._send_standard_headers()

        self.assertIn(("x-request-id", "request-123"), handler.sent_headers)
        self.assertIn(("x-content-type-options", "nosniff"), handler.sent_headers)
        self.assertIn(("x-frame-options", "DENY"), handler.sent_headers)
        self.assertIn(("referrer-policy", "no-referrer"), handler.sent_headers)

    def test_version_and_status_helpers_use_v1_contract(self) -> None:
        handler = _handler()

        self.assertEqual(handler._version_payload()["apiPrefix"], "/api/v1")
        self.assertEqual(handler._version_payload()["apiVersion"], "v1")
        self.assertEqual(handler._dependencies_payload()["llm"], "mock")
        self.assertEqual(handler._health_payload()["ok"], True)

    def test_invalid_json_body_is_rejected(self) -> None:
        handler = _handler()
        handler.headers["content-length"] = "1"
        handler.rfile = BytesIO(b"{")

        with self.assertRaises(BadRequestError):
            handler._read_json_body()

    def test_non_object_json_body_is_rejected(self) -> None:
        handler = _handler()
        handler.headers["content-length"] = "2"
        handler.rfile = BytesIO(b"[]")

        with self.assertRaises(BadRequestError):
            handler._read_json_body()


if __name__ == "__main__":
    unittest.main()
