from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import threading
import unittest
from urllib.request import Request, urlopen

from oci_cost_optimizer.agent_service import create_server as create_agent_server
from oci_cost_optimizer.analytics_service import create_server as create_analytics_server
from oci_cost_optimizer.config import Settings
from oci_cost_optimizer.server import create_server as create_backend_server


def _settings(port: int, *, analytics_url: str = "", agent_url: str = "", llm_provider: str = "mock") -> Settings:
    return Settings(
        app_name="oci-cost-optimizer-test",
        mode="mock",
        data_provider="mock",
        host="127.0.0.1",
        port=port,
        static_root=Path("apps/frontend").resolve(),
        project_root=Path(".").resolve(),
        oci_cli_path=Path("oci"),
        oci_config_file=Path("missing-config"),
        oci_profile="DEFAULT",
        oci_tenancy_ocid="",
        oci_region="",
        oci_user_ocid="",
        oci_fingerprint="",
        oci_key_file=Path(""),
        oci_allow_mock_fallback=True,
        llm_provider=llm_provider,
        openai_api_key_set=False,
        openai_model="gpt-4.1-mini",
        ollama_base_url="http://127.0.0.1:9",
        ollama_model="llama3.2:3b",
        analytics_service_url=analytics_url,
        agent_service_url=agent_url,
        env_file_path=Path(".env"),
        env_file_loaded=False,
    )


def _serve(server) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"content-type": "application/json"},
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


class MicroserviceFunctionalTest(unittest.TestCase):
    def test_backend_delegates_to_analytics_and_agent_services(self) -> None:
        with ExitStack() as stack:
            analytics = create_analytics_server(_settings(0))
            stack.callback(analytics.server_close)
            _serve(analytics)
            analytics_url = f"http://127.0.0.1:{analytics.server_port}"

            agent = create_agent_server(_settings(0, llm_provider="ollama"))
            stack.callback(agent.server_close)
            _serve(agent)
            agent_url = f"http://127.0.0.1:{agent.server_port}"

            backend = create_backend_server(_settings(0, analytics_url=analytics_url, agent_url=agent_url))
            stack.callback(backend.server_close)
            _serve(backend)
            backend_url = f"http://127.0.0.1:{backend.server_port}"

            dashboard = _get_json(f"{backend_url}/api/v1/dashboard?region=all&service=all")
            self.assertEqual(dashboard["meta"]["mode"], "mock")
            self.assertGreater(dashboard["summary"]["openRecommendations"], 0)

            copilot = _post_json(
                f"{backend_url}/api/v1/copilot",
                {"question": "Where can I save the most?", "filters": {"region": "all", "service": "all"}},
            )
            self.assertIn("Potential savings", copilot["answer"])


if __name__ == "__main__":
    unittest.main()
