from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from .config import Settings


def create_setup_status(settings: Settings) -> dict[str, Any]:
    checks = [
        {
            "id": "data_provider",
            "label": "Data provider",
            "ok": settings.data_provider in {"mock", "oci"},
            "value": settings.data_provider,
            "help": "Use DATA_PROVIDER=mock for demo data or DATA_PROVIDER=oci for live OCI data.",
        },
        {
            "id": "oci_cli",
            "label": "OCI CLI path",
            "ok": settings.data_provider != "oci" or _command_exists(settings.oci_cli_path),
            "value": str(settings.oci_cli_path),
            "help": "The container image includes oci. Local runs can install it with .venv/bin/python -m pip install oci-cli.",
        },
        {
            "id": "oci_config",
            "label": "OCI config file",
            "ok": settings.data_provider != "oci" or settings.oci_config_file.is_file(),
            "value": str(settings.oci_config_file),
            "help": "Mount an OCI config to /oci/config or provide OCI_USER_OCID, OCI_FINGERPRINT, OCI_TENANCY_OCID, OCI_REGION, and OCI_KEY_FILE.",
        },
        {
            "id": "oci_profile",
            "label": "OCI profile",
            "ok": bool(settings.oci_profile),
            "value": settings.oci_profile,
            "help": "Use OCI_PROFILE=DEFAULT unless your config file uses another profile.",
        },
        {
            "id": "oci_tenancy",
            "label": "OCI tenancy",
            "ok": settings.data_provider != "oci" or bool(settings.oci_tenancy_ocid),
            "value": "set" if settings.oci_tenancy_ocid else "missing",
            "help": "Set OCI_TENANCY_OCID or include tenancy=... in the OCI config profile.",
        },
        {
            "id": "oci_region",
            "label": "OCI region",
            "ok": settings.data_provider != "oci" or bool(settings.oci_region),
            "value": settings.oci_region or "missing",
            "help": "Set OCI_REGION, for example ap-mumbai-1, or include region=... in the OCI config profile.",
        },
        {
            "id": "oci_key_file",
            "label": "OCI private key file",
            "ok": settings.data_provider != "oci" or bool(settings.oci_key_file) and settings.oci_key_file.is_file(),
            "value": str(settings.oci_key_file) if settings.oci_key_file else "missing",
            "help": "Inside Docker, the key file path must exist inside the container. Prefer mounting ./oci-secrets to /oci.",
        },
    ]
    missing = [check for check in checks if not check["ok"]]

    return {
        "ready": not missing,
        "mode": settings.mode,
        "dataProvider": settings.data_provider,
        "checks": checks,
        "missing": missing,
        "docker": {
            "memoryLimit": "2g",
            "cpuLimit": "1.0",
            "recommendedUrl": "http://127.0.0.1:8080",
        },
    }


def _command_exists(path: Path) -> bool:
    if path.is_absolute() or len(path.parts) > 1:
        return path.is_file()

    return shutil.which(str(path)) is not None
