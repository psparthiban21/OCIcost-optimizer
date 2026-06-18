from __future__ import annotations

import configparser
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    mode: str
    data_provider: str
    host: str
    port: int
    static_root: Path
    project_root: Path
    oci_cli_path: Path
    oci_config_file: Path
    oci_profile: str
    oci_tenancy_ocid: str
    oci_region: str
    oci_user_ocid: str
    oci_fingerprint: str
    oci_key_file: Path


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if len(path.parts) == 1 and not path.is_absolute():
        return path
    return path if path.is_absolute() else project_root / path


def _find_project_root(package_file: Path) -> Path:
    candidates = [package_file.parent, *package_file.parents, Path.cwd()]

    for candidate in candidates:
        if (candidate / "docker-compose.yml").is_file() or (candidate / ".env").is_file():
            return candidate

        if (candidate / "apps").is_dir():
            return candidate

        if (candidate / "src").is_dir() and (candidate / "frontend").is_dir():
            return candidate

    return Path.cwd()


def _read_oci_profile(config_file: Path, profile: str) -> dict[str, str]:
    if not config_file.is_file():
        return {}

    parser = configparser.ConfigParser()
    parser.read(config_file)

    if profile == parser.default_section:
        return dict(parser.defaults())

    if not parser.has_section(profile):
        return {}

    return {key: value for key, value in parser.items(profile)}


def _write_generated_oci_config(project_root: Path, profile: str) -> Path | None:
    required_keys = ["OCI_USER_OCID", "OCI_FINGERPRINT", "OCI_TENANCY_OCID", "OCI_REGION", "OCI_KEY_FILE"]

    if not all(os.getenv(key) for key in required_keys):
        return None

    runtime_dir = Path(os.getenv("OCI_RUNTIME_CONFIG_DIR", "/tmp/oci-cost-optimizer"))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_file = runtime_dir / "config"
    key_file = _project_path(project_root, os.getenv("OCI_KEY_FILE", ""))
    config_file.write_text(
        "\n".join(
            [
                f"[{profile}]",
                f"user={os.getenv('OCI_USER_OCID')}",
                f"fingerprint={os.getenv('OCI_FINGERPRINT')}",
                f"tenancy={os.getenv('OCI_TENANCY_OCID')}",
                f"region={os.getenv('OCI_REGION')}",
                f"key_file={key_file}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    config_file.chmod(0o600)
    return config_file


def load_settings() -> Settings:
    package_file = Path(__file__).resolve()
    project_root = _find_project_root(package_file)
    apps_root = project_root / "apps" if (project_root / "apps").is_dir() else project_root
    _load_env_file(project_root / ".env")
    default_oci_cli = project_root / ".venv" / "bin" / "oci"
    oci_profile = os.getenv("OCI_PROFILE", "DEFAULT")
    configured_oci_config = _project_path(project_root, os.getenv("OCI_CONFIG_FILE", project_root / ".oci" / "config")).resolve()
    generated_oci_config = configured_oci_config if configured_oci_config.is_file() else _write_generated_oci_config(project_root, oci_profile)
    oci_config_file = generated_oci_config or configured_oci_config
    oci_profile_values = _read_oci_profile(oci_config_file, oci_profile)
    key_file_value = oci_profile_values.get("key_file") or os.getenv("OCI_KEY_FILE", "")

    return Settings(
        app_name=os.getenv("APP_NAME", "oci-cost-optimizer-backend"),
        mode=os.getenv("APP_MODE", "mock"),
        data_provider=os.getenv("DATA_PROVIDER", os.getenv("APP_MODE", "mock")).lower(),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "4310")),
        static_root=Path(os.getenv("STATIC_ROOT", apps_root / "frontend")).resolve(),
        project_root=project_root,
        oci_cli_path=_project_path(project_root, os.getenv("OCI_CLI_PATH", default_oci_cli if default_oci_cli.exists() else "oci")),
        oci_config_file=oci_config_file,
        oci_profile=oci_profile,
        oci_tenancy_ocid=os.getenv("OCI_TENANCY_OCID", oci_profile_values.get("tenancy", "")),
        oci_region=os.getenv("OCI_REGION", oci_profile_values.get("region", "")),
        oci_user_ocid=os.getenv("OCI_USER_OCID", oci_profile_values.get("user", "")),
        oci_fingerprint=os.getenv("OCI_FINGERPRINT", oci_profile_values.get("fingerprint", "")),
        oci_key_file=_project_path(project_root, key_file_value) if key_file_value else Path(""),
    )
