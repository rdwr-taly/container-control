from __future__ import annotations

import time
from typing import Any, Dict, List

from app_adapter import ApplicationAdapter


class DummyAdapter(ApplicationAdapter):
    def __init__(self, static_cfg: Dict[str, Any] | None = None) -> None:
        super().__init__(static_cfg)
        self.started_payload: Dict[str, Any] | None = None
        self.stopped = False
        self.updated_payload: Dict[str, Any] | None = None
        self.ensure_user_cmd: List[str] | None = None

    def start(self, start_payload: Dict[str, Any], *, ensure_user) -> Any:
        self.started_payload = start_payload
        # simulate using the ensure_user helper
        self.ensure_user_cmd = ensure_user(["dummy"])
        return "handle"

    def stop(self) -> None:
        self.stopped = True

    def update(self, update_payload: Dict[str, Any]) -> bool:
        self.updated_payload = update_payload
        return update_payload.get("ok", False)

    def get_metrics(self) -> Dict[str, Any]:
        return {"running": not self.stopped}

    def prometheus_metrics(self) -> List[str]:
        return ["dummy_metric 1"]

    def pre_start_hooks(self, start_payload: Dict[str, Any]) -> None:
        # simulate privileged setup delay
        time.sleep(0.01)

    def post_stop_hooks(self) -> None:
        time.sleep(0.01)


class NoUpdateAdapter(DummyAdapter):
    def update(self, update_payload: Dict[str, Any]) -> bool:
        raise NotImplementedError


class ErrorUpdateAdapter(DummyAdapter):
    def update(self, update_payload: Dict[str, Any]) -> bool:
        raise ValueError("boom")
