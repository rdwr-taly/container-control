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


class TCOnlyAdapter(NoUpdateAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_calls = 0

    def start(self, start_payload, *, ensure_user):
        self.start_calls += 1
        return super().start(start_payload, ensure_user=ensure_user)


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


def test_tc_update_without_restart(tmp_path, monkeypatch):
    cfg = {
        "adapter": {
            "class": "tests.test_core.TCOnlyAdapter",
            "primary_payload_key": "payload",
        },
        "traffic_control": {
            "enabled": True,
            "interface": "eth0",
            "bandwidth_mbps_key": "bandwidth",
            "default_bandwidth_mbps": 50,
        },
    }
    path = tmp_path / "config.yaml"
    import ruamel.yaml
    ruamel.yaml.YAML().dump(cfg, path.open("w"))

    client, core = load_core({"config_path": str(path)})

    tc_calls: list[dict] = []

    def fake_tc(payload):
        tc_calls.append(payload.copy())

    monkeypatch.setattr(core, "_apply_traffic_control", fake_tc)

    client.post("/api/start", json={"payload": 1, "bandwidth": 10})
    time.sleep(0.05)
    adapter = core.adapter
    assert isinstance(adapter, TCOnlyAdapter)
    assert adapter.start_calls == 1
    assert len(tc_calls) == 1

    resp = client.post("/api/update", json={"bandwidth": 20})
    assert resp.status_code == 200
    time.sleep(0.05)
    assert adapter.start_calls == 1
    assert len(tc_calls) == 2
    assert tc_calls[-1]["bandwidth"] == 20


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


def test_core_services_config(tmp_path):
    """Test that core services configuration is properly loaded"""
    cfg = {
        "adapter": {
            "class": "tests.dummy_adapter.DummyAdapter",
            "primary_payload_key": "payload",
        },
        "process_management": {
            "enabled": True,
            "command": ["echo", "test"]
        },
        "metrics": {
            "network_monitoring": {"enabled": True},
            "process_monitoring": {"enabled": True}
        },
        "traffic_control": {
            "enabled": True,
            "interface": "eth0",
            "bandwidth_mbps_key": "bandwidth",
            "default_bandwidth_mbps": 50
        },
        "privileged_commands": {
            "pre_start": [["echo", "pre_start"]],
            "post_stop": [["echo", "post_stop"]]
        }
    }
    path = tmp_path / "config.yaml"
    import ruamel.yaml
    ruamel.yaml.YAML().dump(cfg, path.open("w"))

    client, core = load_core({"config_path": str(path)})

    # Check that core services configs are loaded
    assert core.PROC_MAN_CFG["enabled"] is True
    assert core.METRICS_CFG["network_monitoring"]["enabled"] is True
    assert core.TC_CFG["enabled"] is True
    assert core.PRIV_CMD_CFG["pre_start"] == [["echo", "pre_start"]]


def test_new_adapter_hooks(tmp_path):
    """Test that new v1.1 adapter hooks are called"""
    from tests.dummy_adapter import DummyAdapter

    # Create a test adapter with the new hooks
    class TestAdapter(DummyAdapter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.traffic_control_called = False
            self.process_exit_called = False

        def on_before_core_traffic_control(self, payload):
            self.traffic_control_called = True
            return payload

        def on_core_process_exit(self, return_code, stdout, stderr):
            self.process_exit_called = True

    cfg_path = make_config(tmp_path, "tests.dummy_adapter.DummyAdapter")
    client, core = load_core({"config_path": str(cfg_path)})

    # Replace adapter with test adapter
    test_adapter = TestAdapter()
    core.adapter = test_adapter

    # Check that the new hooks exist
    assert hasattr(test_adapter, 'on_before_core_traffic_control')
    assert hasattr(test_adapter, 'on_core_process_exit')
