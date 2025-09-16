"""Utilities for generating Container Control scaffolds.

The functions in this module intentionally mirror the CLI behaviour provided by
:mod:`bootstrap`.  They return byte content so that callers can choose whether
to write to disk, embed the files inside another tool, or perform inspections
during automated reviews.  This mirrors the layout and file contents that ship
on PyPI.  No templating or mutation happens at runtime.
"""

from __future__ import annotations

import importlib.util
from importlib import resources as importlib_resources
from pathlib import Path
import textwrap
from typing import Dict

ScaffoldContents = Dict[str, bytes]
"""Dictionary mapping filenames to their raw bytes in the scaffold."""

WrittenFiles = Dict[str, Path]
"""Dictionary mapping filenames to where they were written on disk."""

_MODULE_TEMPLATES = {
    "container_control_core": "container_control_core.py",
    "app_adapter": "app_adapter.py",
}

_RESOURCE_TEMPLATES = {
    "config.yaml": "config.yaml.example",
    "Dockerfile": "Dockerfile.example",
}

_ADAPTER_STUB = textwrap.dedent(
    """\
    from app_adapter import ApplicationAdapter


    class MyAdapter(ApplicationAdapter):
        def start(self, payload, *, ensure_user):
            raise NotImplementedError

        def stop(self):
            raise NotImplementedError

        def get_metrics(self):
            return {}
    """
)

_TEMPLATES_PACKAGE = "container_control.templates"


class ScaffoldError(RuntimeError):
    """Raised when scaffold assets cannot be located."""


def _load_module_bytes(module_name: str) -> bytes:
    """Return the raw bytes of an importable module.

    The helper keeps :mod:`container_control_core` and :mod:`app_adapter`
    identical across every generated scaffold.  It copies their canonical
    versions directly from the installed distribution.
    """
    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None or spec.loader is None:
        raise ScaffoldError(f"Unable to locate module '{module_name}'")
    loader = spec.loader
    if hasattr(loader, "get_data") and spec.origin:
        return loader.get_data(spec.origin)  # type: ignore[no-any-return]
    return Path(spec.origin).read_bytes()


def _load_resource_bytes(resource_name: str) -> bytes:
    """Return bytes from the package data templates directory."""
    try:
        resource = importlib_resources.files(
            _TEMPLATES_PACKAGE,
        ).joinpath(resource_name)
    except ModuleNotFoundError as exc:  # pragma: no cover - importlib quirk
        raise ScaffoldError(str(exc)) from exc
    if not resource.is_file():
        raise ScaffoldError(f"Resource '{resource_name}' not found")
    return resource.read_bytes()


def render_adapter_stub() -> str:
    """Return the default adapter stub as a string.

    Useful for documentation tooling that wants to display the scaffold without
    writing to disk.
    """

    return _ADAPTER_STUB


def scaffold_files(
    adapter_filename: str | None = "my_adapter.py",
) -> ScaffoldContents:
    """Return the byte representation of the default scaffold files.

    Parameters
    ----------
    adapter_filename:
        Name of the adapter stub file to include. Use ``None`` to skip it.

    Returns
    -------
    dict
        Mapping of filenames to bytes. The dictionary always includes the
        canonical ``container_control_core.py`` and ``app_adapter.py`` modules
        plus the config and Dockerfile templates. The adapter stub is optional.
    """

    files: ScaffoldContents = {}
    for module_name, target_name in _MODULE_TEMPLATES.items():
        files[target_name] = _load_module_bytes(module_name)
    for dest_name, resource_name in _RESOURCE_TEMPLATES.items():
        files[dest_name] = _load_resource_bytes(resource_name)
    if adapter_filename:
        files[adapter_filename] = _ADAPTER_STUB.encode("utf-8")
    return files


def write_scaffold(
    destination: Path | str,
    *,
    adapter_filename: str | None = "my_adapter.py",
) -> WrittenFiles:
    """Write the default scaffold into ``destination``.

    Parameters
    ----------
    destination:
        Directory that should receive the canonical files.
    adapter_filename:
        Optional filename for the adapter stub.
        Passing ``None`` skips creating an adapter.

    Returns
    -------
    dict
        Files that were actually written in this invocation.  Core modules are
        always replaced to guarantee parity with the PyPI release, whereas the
        config, Dockerfile, and adapter stub respect any existing files.
    """

    dest_path = Path(destination)
    dest_path.mkdir(parents=True, exist_ok=True)

    written: WrittenFiles = {}
    files = scaffold_files(adapter_filename)

    for filename, content in files.items():
        path = dest_path / filename
        if filename in _RESOURCE_TEMPLATES and path.exists():
            continue
        if (
            adapter_filename
            and filename == adapter_filename
            and path.exists()
        ):
            continue
        path.write_bytes(content)
        written[filename] = path

    return written


__all__ = [
    "ScaffoldError",
    "render_adapter_stub",
    "scaffold_files",
    "write_scaffold",
]
