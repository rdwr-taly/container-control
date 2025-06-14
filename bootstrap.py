"""Scaffold Container Control integration in a target directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
import textwrap


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy CCC files and create an adapter stub"
    )
    parser.add_argument(
        "target", help="Destination directory for the scaffold"
    )
    parser.add_argument(
        "--adapter", default="my_adapter.py",
        help="Adapter file name to create if missing"
    )
    args = parser.parse_args()

    root = Path(__file__).parent
    dest = Path(args.target).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    for fname in ("container_control_core.py", "app_adapter.py"):
        shutil.copy(root / fname, dest / fname)

    if not (dest / "config.yaml").exists():
        shutil.copy(root / "config.yaml.example", dest / "config.yaml")

    if not (dest / "Dockerfile").exists():
        shutil.copy(root / "Dockerfile.example", dest / "Dockerfile")

    adapter_path = dest / args.adapter
    if not adapter_path.exists():
        stub = textwrap.dedent(
            """
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
        adapter_path.write_text(stub)

    print(f"Container Control scaffold written to {dest}")


if __name__ == "__main__":
    main()
