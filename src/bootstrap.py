"""CLI entry point for generating Container Control scaffolds.

The ``container-control-bootstrap`` console script resolves to :func:`main`. It
exists primarily for developers who prefer a command line interface, whereas
automation or unit tests usually call :func:`container_control.write_scaffold`
directly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from container_control.scaffold import ScaffoldError, write_scaffold


def main() -> None:
    """Parse CLI arguments and write the scaffold to disk."""

    parser = argparse.ArgumentParser(
        description="Copy CCC files and create an adapter stub",
    )
    parser.add_argument(
        "target", help="Destination directory for the scaffold",
    )
    parser.add_argument(
        "--adapter",
        default="my_adapter.py",
        help="Adapter file name to create if missing",
    )
    args = parser.parse_args()

    dest = Path(args.target).resolve()
    try:
        written = write_scaffold(dest, adapter_filename=args.adapter)
    except ScaffoldError as exc:  # pragma: no cover - CLI guard
        raise SystemExit(f"error: {exc}") from exc

    if written:
        print("Created files:")
        for name, path in sorted(written.items()):
            try:
                display = path.relative_to(dest)
            except ValueError:
                display = path
            print(f"  - {display}")

    print(f"Container Control scaffold written to {dest}")


if __name__ == "__main__":
    main()
