from __future__ import annotations

import configparser
from dataclasses import dataclass
import os
from pathlib import Path
import shutil


RUNTIME_DIR = Path(os.getenv("OCI_COST_OPTIMIZER_RUNTIME_DIR", "/tmp/oci-cost-optimizer"))
ENV_FILE_POINTER = RUNTIME_DIR / "env-file-path"


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
    oci_allow_mock_fallback: bool
    llm_provider: str
    openai_api_key_set: bool
    openai_model: str
    ollama_base_url: str
    ollama_model: str
    analytics_service_url: str
    agent_service_url: str
    env_file_path: Path
    env_file_loaded: bool


def _load_env_file(path: Path, *, override: bool = False) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if override:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


def _selected_env_file() -> Path | None:
    env_file = os.getenv("ENV_FILE")

    if env_file:
        return Path(env_file).expanduser()

    if ENV_FILE_POINTER.is_file():
        selected = ENV_FILE_POINTER.read_text(encoding="utf-8").strip()
        return Path(selected).expanduser() if selected else None

    return None


def select_env_file(path: str) -> Path:
    selected = Path(path).expanduser()

    if not selected.is_absolute() and not selected.is_file():
        project_root = _find_project_root(Path(__file__).resolve())
        selected = project_root / selected

    if not selected.is_file():
        raise FileNotFoundError(f"Env file was not found: {selected}")

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    ENV_FILE_POINTER.write_text(str(selected), encoding="utf-8")
    ENV_FILE_POINTER.chmod(0o600)
    _load_env_file(selected, override=True)
    return selected


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


def _first_existing_path(project_root: Path, values: list[str]) -> Path:
    fallback: Path | None = None

    for value in values:
        if not value:
            continue

        path = _project_path(project_root, value)
        if fallback is None:
            fallback = path

        if path.is_file():
            return path

    return fallback or Path("")


def _resolve_oci_cli_path(project_root: Path, configured_value: str | Path) -> Path:
    configured_path = _project_path(project_root, configured_value)

    if configured_path.is_file() or shutil.which(str(configured_path)):
        return configured_path

    if shutil.which("oci"):
        return Path("oci")

    return configured_path


def load_settings() -> Settings:
    package_file = Path(__file__).resolve()
    project_root = _find_project_root(package_file)
    apps_root = project_root / "apps" if (project_root / "apps").is_dir() else project_root
    default_env_file = project_root / ".env"
    selected_env_file = _selected_env_file()
    _load_env_file(default_env_file)

    if selected_env_file:
        _load_env_file(selected_env_file, override=True)

    default_oci_cli = project_root / ".venv" / "bin" / "oci"
    oci_cli_path = _resolve_oci_cli_path(project_root, os.getenv("OCI_CLI_PATH", default_oci_cli if default_oci_cli.exists() else "oci"))
    oci_profile = os.getenv("OCI_PROFILE", "DEFAULT")
    configured_oci_config = _project_path(project_root, os.getenv("OCI_CONFIG_FILE", project_root / ".oci" / "config")).resolve()
    generated_oci_config = configured_oci_config if configured_oci_config.is_file() else _write_generated_oci_config(project_root, oci_profile)
    oci_config_file = generated_oci_config or configured_oci_config
    oci_profile_values = _read_oci_profile(oci_config_file, oci_profile)
    oci_key_file = _first_existing_path(project_root, [oci_profile_values.get("key_file", ""), os.getenv("OCI_KEY_FILE", "")])

    return Settings(
        app_name=os.getenv("APP_NAME", "oci-cost-optimizer-backend"),
        mode=os.getenv("APP_MODE", "mock"),
        data_provider=os.getenv("DATA_PROVIDER", os.getenv("APP_MODE", "mock")).lower(),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "4310")),
        static_root=Path(os.getenv("STATIC_ROOT", apps_root / "frontend")).resolve(),
        project_root=project_root,
        oci_cli_path=oci_cli_path,
        oci_config_file=oci_config_file,
        oci_profile=oci_profile,
        oci_tenancy_ocid=os.getenv("OCI_TENANCY_OCID", oci_profile_values.get("tenancy", "")),
        oci_region=os.getenv("OCI_REGION", oci_profile_values.get("region", "")),
        oci_user_ocid=os.getenv("OCI_USER_OCID", oci_profile_values.get("user", "")),
        oci_fingerprint=os.getenv("OCI_FINGERPRINT", oci_profile_values.get("fingerprint", "")),
        oci_key_file=oci_key_file,
        oci_allow_mock_fallback=os.getenv("OCI_ALLOW_MOCK_FALLBACK", "true").lower() in {"1", "true", "yes", "on"},
        llm_provider=os.getenv("LLM_PROVIDER", "mock").lower(),
        openai_api_key_set=bool(os.getenv("OPENAI_API_KEY")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://host.k3d.internal:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        analytics_service_url=os.getenv("ANALYTICS_SERVICE_URL", "").rstrip("/"),
        agent_service_url=os.getenv("AGENT_SERVICE_URL", "").rstrip("/"),
        env_file_path=selected_env_file or default_env_file,
        env_file_loaded=bool((selected_env_file or default_env_file).is_file()),
    )
