"""High-level entry points for Container Control.

This module deliberately re-exports the handful of symbols that adapter
projects interact with most frequently so that automation agents (human or
otherwise) can inspect the package and immediately discover how to bootstrap a
container.

`ApplicationAdapter`
    Abstract base class that adapters must inherit from.  It documents the
    lifecycle hooks exposed by :mod:`container_control_core`.
`write_scaffold`
    Copy the canonical core files, templates, and adapter stub into a target
    directory.  This is the programmatic counterpart to the
    ``container-control-bootstrap`` CLI.
`scaffold_files` / `render_adapter_stub`
    Lower level helpers that return the same assets without touching the file
    system.

The rest of the modules contained in the package build upon these re-exports.
Keeping the public API surface centralised makes the PyPI distribution easier
to audit and script against.
"""

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
