from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from oci_cost_optimizer.config import _write_runtime_oci_config


class RuntimeOciConfigTests(unittest.TestCase):
    def test_writes_resolved_key_path_with_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            key_file = root / "oci_api_key.pem"
            key_file.write_text("test-key", encoding="utf-8")
            values = {
                "user": "user-ocid",
                "fingerprint": "aa:bb",
                "tenancy": "tenancy-ocid",
                "region": "ap-mumbai-1",
            }

            with patch.dict(os.environ, {"OCI_RUNTIME_CONFIG_DIR": str(root / "runtime")}):
                config_file = _write_runtime_oci_config("DEFAULT", values, key_file)

            self.assertIsNotNone(config_file)
            content = config_file.read_text(encoding="utf-8")
            self.assertIn(f"key_file={key_file}", content)
            self.assertEqual(config_file.stat().st_mode & 0o777, 0o600)

    def test_does_not_write_config_when_key_is_missing(self) -> None:
        values = {
            "user": "user-ocid",
            "fingerprint": "aa:bb",
            "tenancy": "tenancy-ocid",
            "region": "ap-mumbai-1",
        }

        self.assertIsNone(_write_runtime_oci_config("DEFAULT", values, Path("missing-key.pem")))


if __name__ == "__main__":
    unittest.main()
