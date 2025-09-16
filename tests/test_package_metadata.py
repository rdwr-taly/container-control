from __future__ import annotations

import re
from pathlib import Path

import container_control


def test_package_version_matches_pyproject() -> None:
    """Ensure the exposed version matches the published metadata."""

    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"(?P<version>[^\"]+)"',
                      pyproject_text, re.MULTILINE)
    assert match is not None, "version field missing from pyproject"
    assert container_control.__version__ == match.group("version")
