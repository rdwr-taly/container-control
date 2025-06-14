from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Dict

from fastapi.testclient import TestClient


def load_core(config: Dict[str, str]) -> tuple[TestClient, object]:
    cfg_path = Path(config["config_path"])
    os.environ["CCC_CONFIG_FILE"] = str(cfg_path)
    if "container_control_core" in sys.modules:
        del sys.modules["container_control_core"]
    core = importlib.import_module("container_control_core")
    client = TestClient(core.app)
    return client, core
