from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATHS = [
    ROOT / "apps",
    ROOT / "docs",
    ROOT / "infra",
    ROOT / "k8s",
    ROOT / "scripts",
    ROOT / "README.md",
    ROOT / ".env.example",
]

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |PRIVATE )?KEY-----"),
    re.compile(r"OPENAI_API_KEY[ \t]*=[ \t]*(?!$|your-|replace-|example)[A-Za-z0-9_\-]{12,}", re.MULTILINE),
    re.compile(r"ocid1\.[a-z]+\.oc1\.[a-z0-9.-]*\.[a-z0-9]{24,}", re.IGNORECASE),
]

MUTATING_OCI_PATTERNS = [
    re.compile(r"\.delete_[a-z_]+\("),
    re.compile(r"\.terminate_[a-z_]+\("),
    re.compile(r"\.update_instance\("),
    re.compile(r"oci\s+compute\s+instance\s+terminate"),
    re.compile(r"oci\s+compute\s+instance\s+action\s+--action\s+STOP"),
]


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in CHECK_PATHS:
      if path.is_file():
          files.append(path)
      elif path.is_dir():
          files.extend(
              item
              for item in path.rglob("*")
              if item.is_file()
              and ".terraform" not in item.parts
              and "__pycache__" not in item.parts
              and item.name not in {"security_scan.py", "test_security_posture.py"}
              and item.suffix not in {".pyc", ".zip", ".gz", ".tar"}
          )
    return files


def main() -> int:
    failures: list[str] = []

    for path in iter_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"possible secret in {path}: {pattern.pattern}")
        for pattern in MUTATING_OCI_PATTERNS:
            if pattern.search(text):
                failures.append(f"mutating OCI operation in {path}: {pattern.pattern}")

    for manifest in (ROOT / "k8s" / "k3d").glob("*.yaml"):
        text = manifest.read_text(encoding="utf-8")
        if "Deployment" in text and ("limits:" not in text or "runAsNonRoot: true" not in text):
            failures.append(f"missing resource/security controls in {manifest}")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1

    print("Security scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
