from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests.dummy_adapter import DummyAdapter, NoUpdateAdapter, ErrorUpdateAdapter
from tests.conftest import load_core


def make_config(tmp_path: Path, adapter_cls: str, run_as_user: str | None = None) -> Path:
    cfg = {
        "adapter": {
            "class": adapter_cls,
            "primary_payload_key": "payload",
            "run_as_user": run_as_user,
        }
    }
    path = tmp_path / "config.yaml"
    import ruamel.yaml
    ruamel.yaml.YAML().dump(cfg, path.open("w"))
    return path


def test_start_stop_cycle(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, core = load_core({"config_path": str(cfg_path)})

    resp = client.post("/api/start", json={"payload": 1})
    assert resp.status_code == 200
    time.sleep(0.05)
    assert core.state["app_status"] == "running"

    resp = client.post("/api/stop", json={})
    assert resp.status_code == 200
    time.sleep(0.05)
    assert core.state["app_status"] == "stopped"
    assert isinstance(core.adapter, DummyAdapter)
    assert core.adapter.stopped


def test_start_requires_key(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, _ = load_core({"config_path": str(cfg_path)})

    resp = client.post("/api/start", json={})
    assert resp.status_code == 400


def test_update_paths(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, core = load_core({"config_path": str(cfg_path)})

    client.post("/api/start", json={"payload": 1})
    time.sleep(0.05)

    resp = client.post("/api/update", json={"ok": True})
    assert resp.status_code == 200
    assert core.adapter.updated_payload == {"ok": True}

    resp = client.post("/api/update", json={"ok": False})
    assert resp.status_code == 409


def test_update_not_supported(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.NoUpdateAdapter")
    client, _ = load_core({"config_path": str(cfg_path)})

    client.post("/api/start", json={"payload": 1})
    time.sleep(0.05)
    resp = client.post("/api/update", json={"x": 1})
    assert resp.status_code == 409


def test_metrics_and_prometheus(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, _ = load_core({"config_path": str(cfg_path)})

    client.post("/api/start", json={"payload": 1})
    time.sleep(0.05)

    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "timestamp" in data
    assert "metrics" in data

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "container_cpu_percent" in resp.text
    assert "dummy_metric" in resp.text


def test_health_endpoint(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, _ = load_core({"config_path": str(cfg_path)})

    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_run_as_user(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter", "appuser")
    client, core = load_core({"config_path": str(cfg_path)})

    client.post("/api/start", json={"payload": 1})
    time.sleep(0.05)
    assert core.adapter.ensure_user_cmd[:4] == ["sudo", "-E", "-u", "appuser"]


def test_update_requires_running(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, _ = load_core({"config_path": str(cfg_path)})

    resp = client.post("/api/update", json={"x": 1})
    assert resp.status_code == 400


def test_stop_when_not_running(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, _ = load_core({"config_path": str(cfg_path)})

    resp = client.post("/api/stop", json={})
    assert resp.status_code == 200
    assert resp.json()["message"] == "nothing to stop"


def test_restart_cycle(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, core = load_core({"config_path": str(cfg_path)})

    client.post("/api/start", json={"payload": 1})
    time.sleep(0.05)

    client.post("/api/start", json={"payload": 2})
    time.sleep(0.05)
    assert core.adapter.started_payload == {"payload": 2}
    assert core.adapter.stopped


def test_update_exception(tmp_path):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.ErrorUpdateAdapter")
    client, _ = load_core({"config_path": str(cfg_path)})

    client.post("/api/start", json={"payload": 1})
    time.sleep(0.05)
    resp = client.post("/api/update", json={"x": 1})
    assert resp.status_code == 500


def test_ensure_user_non_root(tmp_path, monkeypatch):
    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter", "appuser")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    client, core = load_core({"config_path": str(cfg_path)})

    client.post("/api/start", json={"payload": 1})
    time.sleep(0.05)
    assert core.adapter.ensure_user_cmd == ["dummy"]
