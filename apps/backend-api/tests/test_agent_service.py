from __future__ import annotations

from pathlib import Path
import unittest

from oci_cost_optimizer.agent_service import AgentHandler
from oci_cost_optimizer.config import Settings


def _settings() -> Settings:
    return Settings(
        app_name="oci-cost-optimizer-agent",
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
        oci_allow_mock_fallback=True,
        llm_provider="ollama",
        openai_api_key_set=False,
        openai_model="gpt-4.1-mini",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2:3b",
        analytics_service_url="",
        agent_service_url="",
        env_file_path=Path(".env"),
        env_file_loaded=False,
    )


class AgentServiceTest(unittest.TestCase):
    def test_prompt_keeps_ai_read_only_and_evidence_bound(self) -> None:
        handler = object.__new__(AgentHandler)
        handler.settings = _settings()

        prompt = handler._build_prompt("Where can I save money?", {"region": "all", "service": "Compute"}, "fallback")

        self.assertIn("Use only the provided cost data", prompt)
        self.assertIn("Do not claim that resources were changed", prompt)
        self.assertIn("Do not recommend automatic deletion", prompt)
        self.assertIn("identified_savings", prompt)


if __name__ == "__main__":
    unittest.main()
