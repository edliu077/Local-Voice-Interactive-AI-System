"""Strict local configuration for the Demo Stable workspace."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


LOOPBACK_HOST = "127.0.0.1"


def project_root(source_file: str | Path) -> Path:
    configured = os.environ.get("LVIAI_PROJECT_ROOT", "").strip()
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            raise RuntimeError("LVIAI_PROJECT_ROOT must be an absolute path")
        root = candidate.resolve()
    else:
        root = Path(source_file).resolve().parents[2]
    if not root.is_dir():
        raise FileNotFoundError(f"Demo Stable project root does not exist: {root}")
    return root


def configured_path(name: str, default: Path) -> Path:
    configured = os.environ.get(name, "").strip()
    if not configured:
        return default.resolve()
    candidate = Path(configured)
    if not candidate.is_absolute():
        raise RuntimeError(f"{name} must be an absolute path")
    return candidate.resolve()


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    return path


def require_directory(path: Path, label: str) -> Path:
    if not path.is_dir():
        raise FileNotFoundError(f"{label} is missing: {path}")
    return path


def loopback_host(name: str) -> str:
    value = os.environ.get(name, LOOPBACK_HOST).strip()
    if value != LOOPBACK_HOST:
        raise RuntimeError(f"{name} must remain {LOOPBACK_HOST} for Demo Stable")
    return value


def port(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not 1 <= value <= 65535:
        raise RuntimeError(f"{name} must be between 1 and 65535")
    return value


def allowed_frontend_origins(frontend_port: int) -> tuple[str, ...]:
    default = f"http://127.0.0.1:{frontend_port},http://localhost:{frontend_port}"
    raw = os.environ.get("LVIAI_ALLOWED_ORIGINS", default)
    origins = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not origins:
        raise RuntimeError("LVIAI_ALLOWED_ORIGINS must contain at least one local origin")
    for origin in origins:
        parsed = urlparse(origin)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.port != frontend_port
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
            or "*" in origin
        ):
            raise RuntimeError(
                "LVIAI_ALLOWED_ORIGINS may contain only the configured local frontend origins"
            )
    return origins

