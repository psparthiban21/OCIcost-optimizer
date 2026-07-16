from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from oci_cost_optimizer.config import Settings
from oci_cost_optimizer.server import create_server


def _settings(port: int) -> Settings:
    return Settings(
        app_name="oci-cost-optimizer-test",
        mode="mock",
        data_provider="mock",
        host="127.0.0.1",
        port=port,
        static_root=(Path(__file__).resolve().parents[4] / "apps" / "frontend").resolve(),
        project_root=Path(".").resolve(),
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
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2:3b",
        analytics_service_url="",
        agent_service_url="",
        env_file_path=Path(".env"),
        env_file_loaded=False,
    )


def _serve(server) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


class HttpPenetrationTest(unittest.TestCase):
    def test_static_path_traversal_is_not_served(self) -> None:
        with ExitStack() as stack:
            server = create_server(_settings(0))
            stack.callback(server.server_close)
            _serve(server)
            base_url = f"http://127.0.0.1:{server.server_port}"

            for path in ["/../.env", "/%2e%2e/.env", "/../../../../etc/passwd"]:
                with self.subTest(path=path):
                    with self.assertRaises(HTTPError) as raised:
                        urlopen(f"{base_url}{path}", timeout=5)
                    self.assertEqual(raised.exception.code, 404)

    def test_oversized_json_body_is_rejected(self) -> None:
        with ExitStack() as stack:
            server = create_server(_settings(0))
            stack.callback(server.server_close)
            _serve(server)
            base_url = f"http://127.0.0.1:{server.server_port}"

            payload = {"question": "x" * (70 * 1024)}
            request = Request(
                f"{base_url}/api/v1/copilot",
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={"content-type": "application/json"},
            )

            with self.assertRaises(HTTPError) as raised:
                urlopen(request, timeout=5)

            self.assertEqual(raised.exception.code, 400)


if __name__ == "__main__":
    unittest.main()

