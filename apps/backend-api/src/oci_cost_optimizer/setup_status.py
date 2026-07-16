from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from .config import Settings


def create_setup_status(settings: Settings) -> dict[str, Any]:
    checks = [
        {
            "id": "env_file",
            "label": "Environment file",
            "ok": True,
            "value": str(settings.env_file_path) if settings.env_file_loaded else "not loaded; using process environment",
            "help": "Optional. Create a .env file, then open /setup.html and provide its path. Docker Compose mounts your home directory read-only, so host paths under your home can be entered directly.",
        },
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
            "help": "Inside Docker, the key file path must exist inside the container. Compose mounts your home directory read-only, so a host key path under your home can be used directly.",
        },
        {
            "id": "llm_provider",
            "label": "LLM provider",
            "ok": settings.llm_provider in {"mock", "openai", "ollama"},
            "value": settings.llm_provider,
            "help": "Use LLM_PROVIDER=mock for deterministic local answers, LLM_PROVIDER=ollama for local AI, or LLM_PROVIDER=openai for OpenAI-backed recommendations.",
        },
        {
            "id": "openai_api_key",
            "label": "OpenAI API key",
            "ok": settings.llm_provider != "openai" or settings.openai_api_key_set,
            "value": "set" if settings.openai_api_key_set else "missing",
            "help": "Set OPENAI_API_KEY in .env only. Do not put API keys in README, source code, or Git.",
        },
        {
            "id": "openai_model",
            "label": "OpenAI model",
            "ok": settings.llm_provider != "openai" or bool(settings.openai_model),
            "value": settings.openai_model or "missing",
            "help": "Set OPENAI_MODEL to the model used for LLM recommendations.",
        },
    ]
    missing = [check for check in checks if not check["ok"]]

    return {
        "ready": not missing,
        "mode": settings.mode,
        "dataProvider": settings.data_provider,
        "envFile": {
            "loaded": settings.env_file_loaded,
            "path": str(settings.env_file_path) if settings.env_file_loaded else None,
        },
        "checks": checks,
        "missing": missing,
        "docker": {
            "memoryLimit": "2g",
            "cpuLimit": "1.0",
            "recommendedUrl": "http://127.0.0.1:8080",
        },
        "assistance": {
            "newLaptop": [
                "Run in mock mode first: DATA_PROVIDER=mock and LLM_PROVIDER=mock.",
                "Open /setup.html to provide any .env file path after creating it. With Docker Compose, host paths under your home are mounted read-only at the same path.",
                "For OCI live mode, create an OCI config and private key either under your home directory or in the repo .oci folder.",
                "Inside Docker, OCI config key_file must point to a path visible inside the container. With Compose, host paths under your home are mounted read-only at the same path.",
                "For OpenAI recommendations, set LLM_PROVIDER=openai and OPENAI_API_KEY in .env.",
            ],
            "ociRequiredEnv": [
                "DATA_PROVIDER=oci",
                "OCI_USER_OCID",
                "OCI_FINGERPRINT",
                "OCI_TENANCY_OCID",
                "OCI_REGION",
                "OCI_KEY_FILE=/Users/name/path/to/oci_api_key.pem",
            ],
            "openaiRequiredEnv": [
                "LLM_PROVIDER=openai",
                "OPENAI_API_KEY",
                "OPENAI_MODEL",
            ],
        },
    }


def _command_exists(path: Path) -> bool:
    if path.is_absolute() or len(path.parts) > 1:
        return path.is_file()

    return shutil.which(str(path)) is not None
