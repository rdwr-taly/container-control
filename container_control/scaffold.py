"""Utilities for generating Container Control scaffolds."""

from __future__ import annotations

import importlib.util
from importlib import resources as importlib_resources
from pathlib import Path
import textwrap
from typing import Dict

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
    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None or spec.loader is None:
        raise ScaffoldError(f"Unable to locate module '{module_name}'")
    loader = spec.loader
    if hasattr(loader, "get_data") and spec.origin:
        return loader.get_data(spec.origin)  # type: ignore[no-any-return]
    return Path(spec.origin).read_bytes()


def _load_resource_bytes(resource_name: str) -> bytes:
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
    """Return the default adapter stub as a string."""

    return _ADAPTER_STUB


def scaffold_files(adapter_filename: str | None = "my_adapter.py") -> Dict[str, bytes]:
    """Return the files that make up a default scaffold.

    Parameters
    ----------
    adapter_filename:
        Name of the adapter stub file to include. Use ``None`` to skip it.
    """

    files: Dict[str, bytes] = {}
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
) -> Dict[str, Path]:
    """Write the default scaffold into ``destination``.

    Core modules are always overwritten. The config, Dockerfile, and adapter
    stub are created only if the destination file does not already exist.
    Returns a mapping of filenames to their on-disk paths for the files that
    were written during this invocation.
    """

    dest_path = Path(destination)
    dest_path.mkdir(parents=True, exist_ok=True)

    written: Dict[str, Path] = {}
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
