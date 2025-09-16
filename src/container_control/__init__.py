"""Public interface for the Container Control package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from app_adapter import ApplicationAdapter

from .scaffold import render_adapter_stub, scaffold_files, write_scaffold

try:
    __version__ = version("container-control")
except PackageNotFoundError:  # pragma: no cover - fallback during local dev
    __version__ = "1.1.0"

__all__ = [
    "ApplicationAdapter",
    "render_adapter_stub",
    "scaffold_files",
    "write_scaffold",
    "__version__",
]
