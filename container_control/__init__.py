"""Public interface for the Container Control package."""

from __future__ import annotations

from app_adapter import ApplicationAdapter

from .scaffold import render_adapter_stub, scaffold_files, write_scaffold

__all__ = [
    "ApplicationAdapter",
    "render_adapter_stub",
    "scaffold_files",
    "write_scaffold",
]
