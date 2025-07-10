# Container Control

**One immutable core + lightweight adapter + optional services = zero boilerplate.**

This repository explains how to integrate any containerised workload with Showrunner using the **Container Control Core (CCC) v2.0**.

The core now provides optional built-in services for process management, metrics collection, traffic control, and privileged operations - reducing the complexity of your adapters even further.

---

## Contents

1. [Concept](#concept)
2. [Files You Care About](#files-you-care-about)
3. [Core Services](#core-services)
4. [Quickstart (`bootstrap.py`)](#quickstart-bootstrappy)
5. [Building an Adapter](#building-an-adapter)
6. [Configuration (`config.yaml`)](#configuration-configyaml)
7. [Dockerfile Template](#dockerfile-template)
8. [API Reference](#api-reference)
9. [Operational Tips](#operational-tips)

---

## Concept

```
(root, FastAPI)
┌──────────────────────────────────────────┐
│ container_control_core.py (v2.0)         │
│ • HTTP API (/api/*, /metrics)            │
│ • lifecycle / state / signals            │
│ • container-level metrics                │
│ • privilege separation helper            │
│ • OPTIONAL SERVICES:                     │
│   - Process Management                   │
│   - Enhanced Metrics Collection          │
│   - Traffic Control (tc)                 │
│   - Privileged Commands                  │
└──────────────┬───────────────────────────┘
              │ imports adapter class
              ▼
 app_adapter.py  ← common interface
              │ subclassed by you
              ▼
 my_adapter.py  ← 5‑30 LOC typical (v2.0)
              │ calls (if needed)
              ▼
Your real workload (async code, binary, …)
```

*All containers share the **exact same** `container_control_core.py` v2.0; only `my_adapter.py` and `config.yaml` vary per application. The core's optional services can eliminate most boilerplate code.*

---

## Files You Care About

| File                        | Keep unmodified? | Purpose                                                             |
|-----------------------------|------------------|---------------------------------------------------------------------|
| `container_control_core.py` | **Yes**          | FastAPI service including the `/api/update` endpoint.               |
| `app_adapter.py`            | **Yes**          | Abstract base class defining the contract.                          |
| `my_adapter.py`             | No               | Your shim – implements the contract.                                |
| `config.yaml`               | No               | Declares which adapter to load & options.                           |
| `Dockerfile`                | No               | Builds the image using the template below.                          |

---

## Core Services

Container Control Core v2.0 includes optional built-in services that can handle common container operations, reducing the complexity of your adapters:

### Process Management Service
- **Purpose**: Let the core manage your application process lifecycle
- **Benefits**: Automatic process monitoring, graceful shutdown, PID tracking
- **Configuration**: `process_management.enabled: true`
- **Use case**: When your workload is a simple command/binary

### Enhanced Metrics Service  
- **Purpose**: Automatic collection of network and process metrics
- **Benefits**: Zero-code monitoring, Prometheus-compatible output
- **Configuration**: `metrics.network_monitoring.enabled: true`
- **Use case**: When you need standard container metrics without custom code

### Traffic Control Service
- **Purpose**: Built-in network shaping using Linux `tc` 
- **Benefits**: Bandwidth limiting, latency simulation, no custom networking code
- **Configuration**: `traffic_control.enabled: true`
- **Requirements**: `CAP_NET_ADMIN` capability, `iproute2` package

### Privileged Commands Service
- **Purpose**: Declarative execution of privileged commands at lifecycle events
- **Benefits**: System tuning, firewall rules, network setup without custom hooks
- **Configuration**: `privileged_commands.pre_start: [...]`
- **Use case**: When you need root-level system configuration

---

## Quickstart (`bootstrap.py`)

Run the helper script to copy the core files into your project:

```bash
python bootstrap.py /path/to/your/app
```

This creates `container_control_core.py`, `app_adapter.py`, `config.yaml`,
and a skeleton adapter.  A Dockerfile is also copied if none exists.

---

## Building an Adapter

Copy `app_adapter.py` into your repo, then create `my_adapter.py`. With v2.0's core services, adapters can be much simpler:

### Simple Adapter (using core services)
```python
from app_adapter import ApplicationAdapter

class MyAdapter(ApplicationAdapter):
    def start(self, payload, *, ensure_user):
        # With process_management.enabled: true, this can be empty!
        # The core handles the process based on config.yaml
        return None  # Core manages everything

    def stop(self):
        # With process_management.enabled: true, this can be empty!
        pass

    def get_metrics(self):
        # With metrics services enabled, just return app-specific metrics
        return {"custom_metric": self.get_some_value()}
```

### Traditional Adapter (manual process management)
```python
from __future__ import annotations
import subprocess
from app_adapter import ApplicationAdapter

class MyAdapter(ApplicationAdapter):
    def start(self, payload, *, ensure_user):
        cmd = ["python3", "my_tool.py", "--flows", payload["flowfile"]]
        self.proc = subprocess.Popen(ensure_user(cmd))
        return self.proc  # opaque handle

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=5)

    def update(self, payload):
        level = payload.get("log_level")
        if level is None:
            return False
        subprocess.run(["kill", "-USR1", str(self.proc.pid)])
        return True

    def get_metrics(self):
        return {"running": self.proc.poll() is None}

    def pre_start_hooks(self, payload):
        # example privileged setup
        bw = payload.get("bandwidth", 20)
        subprocess.run(
            ["tc", "qdisc", "add", "dev", "eth0", "root",
             "tbf", "rate", f"{bw}mbit", "latency", "50ms", "burst", "32k"],
            check=True,
        )
```

**v2.0 adapter size**: Often < 15 lines when using core services!
**Traditional adapter size**: 20-40 lines when managing everything manually.

---

## Configuration (`config.yaml`)

### Minimal Configuration
```yaml
adapter:
  class: my_adapter.MyAdapter      # dotted-path import
  primary_payload_key: flowfile    # key that must exist in /api/start body
  run_as_user: app_user            # null ⇒ run as root
```

### Full Configuration (with core services)
```yaml
# --- Adapter Configuration (Required) ---
adapter:
  class: my_adapter.MyAdapter
  primary_payload_key: target_url
  run_as_user: app_user

# --- Core Process Management (Optional) ---
process_management:
  enabled: true
  # Use command_factory for dynamic commands (recommended)
  command_factory: "my_adapter.MyAdapter.build_command"
  # OR use static template commands
  # command: ["./my-tool", "--url", "{target_url}", "--threads", "{threads}"]

# --- Core Metrics Service (Optional) ---
metrics:
  network_monitoring:
    enabled: true
    interface: "eth0"
  process_monitoring:
    enabled: true  # Only works with process_management enabled

# --- Core Traffic Control (Optional) ---
traffic_control:
  enabled: true
  interface: "eth0"
  bandwidth_mbps_key: "bandwidth_limit"
  default_bandwidth_mbps: 50
  latency_ms_key: "latency"
  default_latency_ms: 20

# --- Privileged Commands (Optional) ---
privileged_commands:
  pre_start:
    - ["sysctl", "-w", "net.core.somaxconn=4096"]
    - ["iptables", "-A", "INPUT", "-m", "conntrack", "--ctstate", "ESTABLISHED", "-j", "ACCEPT"]
  post_stop:
    - ["iptables", "-F"]
```

If your workload never needs privilege-drop, omit `run_as_user`. If using core services, your adapter can be much simpler.

---

## Dockerfile Template

```dockerfile
FROM python:3.11-slim
ENV TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Required for traffic control and privileged commands services
RUN apt-get update && apt-get install -y --no-install-recommends \
      iproute2 iptables sudo && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ARG APP_USER=app_user
RUN useradd -ms /bin/bash ${APP_USER} && \
    echo "${APP_USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn psutil ruamel.yaml

# --- Core + interface + adapter + config
COPY container_control_core.py .
COPY app_adapter.py .
COPY my_adapter.py .
COPY config.yaml .

# --- Your actual application source/binaries
COPY . .

# Requires CAP_NET_ADMIN for traffic control service
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "container_control_core:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## API Reference

| Method | Path          | Description                                                                                         |
|--------|---------------|-----------------------------------------------------------------------------------------------------|
| `POST` | `/api/start`  | Start the workload (or restart if running). Payload must include the key named in `config.yaml`.   |
| `POST` | `/api/update` | Live config tweak. Returns 200 on success, 409 if unsupported, 400 if the app is not running.       |
| `POST` | `/api/stop`   | Graceful stop.                                                                                      |
| `GET`  | `/api/metrics`| JSON with container + adapter metrics.                                                              |
| `GET`  | `/metrics`    | Prometheus exposition.                                                                              |
| `GET`  | `/api/health` | Simple liveness check.                                                                              |

All timestamps are UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SS.mmmmmmZ`).

---

## Operational Tips

### Container Deployment
- **Kubernetes readiness probe** → `/api/health`
- **Horizontal scaling**: watch `cpu_percent` from `/api/metrics`
- **Security**: Core services handle privileged operations; main workload runs as `app_user`
- **Capabilities**: Add `CAP_NET_ADMIN` if using traffic control service

### Monitoring & Metrics
- **Prometheus scraping** → `/metrics` endpoint
- **Core metrics**: CPU, memory, network I/O automatically included
- **Process metrics**: Available when using `process_management` service
- **Custom metrics**: Return from your adapter's `get_metrics()` method

### Configuration Management
- **Environment**: Set `CCC_CONFIG_FILE=/path/to/config.yaml` to override config location
- **Logging**: Set `LOG_LEVEL=DEBUG` for detailed core service logs
- **Process management**: Use `command_factory` for dynamic command generation

### Core Services Best Practices
- **Process Management**: Use for simple binaries/commands; traditional adapters for complex async code
- **Traffic Control**: Requires `CAP_NET_ADMIN` and `iproute2` package
- **Privileged Commands**: Use for system tuning, firewall rules, network setup
- **Metrics**: Enable network/process monitoring for zero-code observability

### Upgrading
- **Core updates**: Replace `container_control_core.py` in the image
- **Adapter compatibility**: v2.0 is backward compatible with v1.x adapters
- **New services**: Add optional service configs without breaking existing deployments

Happy Showrunning! :clapper:

