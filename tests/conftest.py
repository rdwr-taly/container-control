from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if SRC_PATH.exists():
    src_str = str(SRC_PATH)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

from fastapi.testclient import TestClient


def load_core(config: Dict[str, str]) -> tuple[TestClient, object]:
    cfg_path = Path(config["config_path"])
    os.environ["CCC_CONFIG_FILE"] = str(cfg_path)
    if "container_control_core" in sys.modules:
        del sys.modules["container_control_core"]
    core = importlib.import_module("container_control_core")
    client = TestClient(core.app)
    return client, core
