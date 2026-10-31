"""
Render bolna-agents/bolna_agent_config.template.json into the importable
bolna-agents/bolna_agent_config.json by substituting {{BACKEND_PUBLIC_URL}}
and {{BOLNA_WEBHOOK_SECRET}} from the backend .env file.

Run this after setting BACKEND_PUBLIC_URL in backend/.env and before importing
the agent into Bolna. The rendered file is gitignored so real URLs and secrets
are never committed.

Usage (from repo root):
    cd backend
    python -m scripts.render_bolna_config

Or from any directory:
    python backend/scripts/render_bolna_config.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ── Path resolution ──────────────────────────────────────────────────────────

# Support running as `python -m scripts.render_bolna_config` from backend/
# or as a standalone script from anywhere.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
_BACKEND_ROOT = _HERE.parent

_TEMPLATE = _REPO_ROOT / "bolna-agents" / "bolna_agent_config.template.json"
_OUTPUT = _REPO_ROOT / "bolna-agents" / "bolna_agent_config.json"
_ENV_FILE = _BACKEND_ROOT / ".env"


def _load_env_file(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a key→value dict; skip comments and blank lines."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            env[key.strip()] = value.strip()
    return env


def main() -> None:
    if not _TEMPLATE.exists():
        print(f"ERROR: template not found at {_TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    # Load values: env file first, then override with actual process environment
    env = _load_env_file(_ENV_FILE)
    backend_url = os.environ.get("BACKEND_PUBLIC_URL") or env.get("BACKEND_PUBLIC_URL", "")
    webhook_secret = os.environ.get("BOLNA_WEBHOOK_SECRET") or env.get("BOLNA_WEBHOOK_SECRET", "")

    warnings: list[str] = []
    if not backend_url:
        warnings.append(
            "WARNING: BACKEND_PUBLIC_URL is not set. "
            "The rendered file will still contain a {{BACKEND_PUBLIC_URL}} placeholder. "
            "Set it in backend/.env and re-run this script before importing into Bolna."
        )
    if not webhook_secret:
        warnings.append(
            "WARNING: BOLNA_WEBHOOK_SECRET is not set. "
            "The rendered file will still contain a {{BOLNA_WEBHOOK_SECRET}} placeholder. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    template_text = _TEMPLATE.read_text(encoding="utf-8")

    rendered = template_text
    if backend_url:
        rendered = rendered.replace("{{BACKEND_PUBLIC_URL}}", backend_url)
    if webhook_secret:
        rendered = rendered.replace("{{BOLNA_WEBHOOK_SECRET}}", webhook_secret)

    # Validate the result is parseable JSON
    try:
        parsed = json.loads(rendered)
    except json.JSONDecodeError as exc:
        print(f"ERROR: rendered output is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    # Detect any remaining unresolved placeholders
    remaining = re.findall(r"\{\{[^}]+\}\}", rendered)
    if remaining:
        print(
            "ERROR: rendered output still contains unresolved placeholders: "
            + ", ".join(set(remaining)),
            file=sys.stderr,
        )
        for w in warnings:
            print(w, file=sys.stderr)
        sys.exit(1)

    _OUTPUT.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Rendered: {_TEMPLATE.name} -> {_OUTPUT}")
    print(f"Output  : {_OUTPUT}")
    print(f"Unresolved placeholders: 0 [OK]")

    if backend_url:
        print(f"BACKEND_PUBLIC_URL : {backend_url}")
    if webhook_secret:
        print(f"BOLNA_WEBHOOK_SECRET: ***{webhook_secret[-4:]}")

    for w in warnings:
        print(w)


if __name__ == "__main__":
    main()
