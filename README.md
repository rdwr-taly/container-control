# Container Control

**One immutable core + lightweight adapter + optional services = zero boilerplate.**

This repository explains how to integrate any containerised workload with Showrunner using the **Container Control Core (CCC) v1.1**.

The core now provides optional built-in services for process management, metrics collection, traffic control, and privileged operations - reducing the complexity of your adapters even further.

---

## Contents

1. [Concept](#concept)
2. [Repository Layout](#repository-layout)
3. [Files You Care About](#files-you-care-about)
4. [Core Services](#core-services)
5. [Installation](#installation)
6. [Quickstart (`container-control-bootstrap`)](#quickstart-container-control-bootstrap)
7. [Building an Adapter](#building-an-adapter)
8. [Configuration (`config.yaml`)](#configuration-configyaml)
9. [Dockerfile Template](#dockerfile-template)
10. [API Reference](#api-reference)
11. [Operational Tips](#operational-tips)
12. [Publishing to PyPI](#publishing-to-pypi)

---

## Concept

```
(root, FastAPI)
┌──────────────────────────────────────────┐
│ container_control_core.py (v1.1)         │
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
 my_adapter.py  ← 5‑30 LOC typical (v1.1)
              │ calls (if needed)
              ▼
Your real workload (async code, binary, …)
```

*All containers share the **exact same** `container_control_core.py` v1.1; only `my_adapter.py` and `config.yaml` vary per application. The core's optional services can eliminate most boilerplate code.*

---

## Repository Layout

This project follows the standard `src/` layout so the packaged wheel and the
checked-out repository have the same module structure:

```text
src/
├── app_adapter.py
├── bootstrap.py
├── container_control/
│   ├── __init__.py
│   ├── scaffold.py
│   └── templates/
│       ├── Dockerfile.example
│       └── config.yaml.example
└── container_control_core.py
```

Working inside a clone, install dependencies with `pip install -e .` so the
`src/` directory is on the Python path. The automated test suite mirrors this
layout by placing `src/` at the front of `sys.path`.

### Code map for automation & code-reading agents

Agents or humans inspecting the published wheel will see the same structure as
the source tree above. The key modules and the responsibilities they cover are:

| Module | What it provides | Typical consumers |
| --- | --- | --- |
| `container_control_core` | The FastAPI service. Hosts REST, Prometheus, optional process/metrics/traffic/privileged services. | Runtime containers only. The file ships verbatim so adapters can rely on a stable API. |
| `app_adapter` | Abstract base class adapters must subclass. Documents lifecycle hooks such as `start`, `stop`, and `update`. | Adapter authors. Keep this file identical across services. |
| `bootstrap` | CLI entry point `container-control-bootstrap`. Calls `write_scaffold()` to copy the canonical files into a target directory. | Developers who want to initialise a project or refresh the canonical files. |
| `container_control/__init__.py` | Convenience exports so `from container_control import write_scaffold` works without drilling into submodules. Also exposes the installed version. | Library users and automation tools. |
| `container_control/scaffold.py` | The implementation behind scaffolding helpers. Loads byte-for-byte copies of the canonical modules and resource templates. | CLI + advanced users needing programmatic access. |
| `container_control/templates/` | Template assets for `config.yaml` and the Dockerfile example. | Scaffolding utilities. |

When browsing the wheel contents you can therefore start with
`container_control_core` to understand the runtime API and then follow imports
into `app_adapter` to see the adapter contract. The remaining modules focus on
setting up those two canonical files.

---

## Files You Care About

*In this repository the canonical source files live under `src/`, but the
scaffold command copies them into the destination project root.*

| File                        | Keep unmodified? | Purpose                                                             |
|-----------------------------|------------------|---------------------------------------------------------------------|
| `container_control_core.py` | **Yes**          | FastAPI service including the `/api/update` endpoint.               |
| `app_adapter.py`            | **Yes**          | Abstract base class defining the contract.                          |
| `my_adapter.py`             | No               | Your shim – implements the contract.                                |
| `config.yaml`               | No               | Declares which adapter to load & options.                           |
| `Dockerfile`                | No               | Builds the image using the template below.                          |

---

## Core Services

Container Control Core v1.1 includes optional built-in services that can handle common container operations, reducing the complexity of your adapters:

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

## Installation

Install the core and scaffolding tools directly from PyPI:

```bash
pip install container-control
```

This installs the runtime modules (`container_control_core.py`,
`app_adapter.py`, the optional FastAPI application) along with helper
templates and a Bootstrap CLI.  You can also import
`container_control.ApplicationAdapter` or the scaffolding helpers from
Python code.

---

## Quickstart (`container-control-bootstrap`)

Run the helper CLI to copy the core files into your project:

```bash
container-control-bootstrap /path/to/your/app
```

This creates `container_control_core.py`, `app_adapter.py`, `config.yaml`,
and a skeleton adapter.  A Dockerfile is also copied if none exists.
Pass `--adapter other_name.py` to pick a different adapter filename.  The
command only generates the config, Dockerfile, and adapter stub if those
files are missing so that you can re-run it safely to refresh the core
modules.

Programmatic scaffolding is available via:

```python
from container_control import write_scaffold

write_scaffold("/path/to/your/app")
```

---

## Building an Adapter

Copy `app_adapter.py` into your repo, then create `my_adapter.py`. With v1.1's core services, adapters can be much simpler:

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

**v1.1 adapter size**: Often < 15 lines when using core services!
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
| `POST` | `/api/update` | Live config tweak (e.g., traffic control) without restart. Returns 200 on success, 409 if unsupported, 400 if the app is not running. |
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
- **Adapter compatibility**: v1.1 is backward compatible with v1.x adapters
- **New services**: Add optional service configs without breaking existing deployments

## Publishing to PyPI

Container Control is published through the manual **Publish to PyPI**
workflow (`.github/workflows/publish.yml`). The job uses PyPI's Trusted
Publishers integration with GitHub OpenID Connect, so no long-lived API
tokens are stored in the repository.

### One-time setup

1. In **Settings → Environments**, create an environment named `pypi` and set
   the environment URL to <https://pypi.org/project/container-control/>.
2. On PyPI, add a Trusted Publisher with the following values:
   - **PyPI project name**: `container-control`
   - **Owner**: `rdwr-taly`
   - **Repository name**: `container-control`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. (Optional) Require reviewers or branch protections on the `pypi`
   environment before the workflow can deploy.

No repository secrets or variables are required; PyPI issues a short-lived
token to the workflow at runtime via OIDC.

### Releasing

1. Update `CHANGELOG.md` and bump the version in `pyproject.toml`.
2. Run the test suite (`pytest`) to confirm behaviour before publishing.
3. Trigger **Publish to PyPI** from the *Actions* tab and supply the version
   from `pyproject.toml` when prompted.
4. The workflow builds fresh distributions with `python -m build` and, after
   the environment approval (if configured), uploads them to PyPI.

Happy Showrunning! :clapper:

