from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


class SecurityPostureTest(unittest.TestCase):
    def test_k3d_manifests_use_non_root_and_resource_limits(self) -> None:
        for manifest in (ROOT / "k8s" / "k3d").glob("*.yaml"):
            if manifest.name in {"namespace.yaml", "configmap.yaml", "kustomization.yaml", "network-policy.yaml"}:
                continue

            text = manifest.read_text(encoding="utf-8")
            self.assertIn("runAsNonRoot: true", text, manifest)
            self.assertIn("allowPrivilegeEscalation: false", text, manifest)
            self.assertIn("drop: [\"ALL\"]", text, manifest)
            self.assertIn("requests:", text, manifest)
            self.assertIn("limits:", text, manifest)

    def test_no_mutating_oci_commands_are_exposed_in_backend_source(self) -> None:
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "apps" / "backend-api" / "src").rglob("*.py"))
        forbidden = [
            ".delete_",
            ".terminate_",
            ".update_instance",
            ".remove_",
            "oci compute instance terminate",
            "oci compute instance action --action STOP",
        ]

        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
