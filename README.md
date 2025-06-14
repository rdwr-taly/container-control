# Container Control

**One immutable core + lightweight adapter = zero boilerplate.**

This repository explains how to integrate any containerised workload with Showrunner using the **Container Control Core (CCC)**.

---

## Contents

1. [Concept](#concept)
2. [Files You Care About](#files-you-care-about)
3. [Building an Adapter](#building-an-adapter)
4. [Configuration (`config.yaml`)](#configuration-configyaml)
5. [Dockerfile Template](#dockerfile-template)
6. [API Reference](#api-reference)
7. [Operational Tips](#operational-tips)

---

## Concept

```
(root, FastAPI)
┌──────────────────────────────────────────┐
│ container_control_core.py                │
│ • HTTP API (/api/*, /metrics)            │
│ • lifecycle / state / signals            │
│ • container-level metrics                │
│ • privilege separation helper            │
└──────────────┬───────────────────────────┘
              │ imports adapter class
              ▼
 app_adapter.py  ← common interface
              │ subclassed by you
              ▼
 my_adapter.py  ← 15‑40 LOC typical
              │ calls
              ▼
Your real workload (async code, binary, …)
```

*All containers share the **exact same** `container_control_core.py`; only `my_adapter.py` and `config.yaml` vary per application.*

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

## Building an Adapter

Copy `app_adapter.py` into your repo, then create `my_adapter.py`:

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

Typical adapter size: < 40 lines.

---

## Configuration (`config.yaml`)

```yaml
adapter:
  class: my_adapter.MyAdapter      # dotted-path import
  primary_payload_key: flowfile    # key that must exist in /api/start body
  run_as_user: app_user            # null ⇒ run as root
```

If your workload never needs privilege-drop, omit `run_as_user`.

---

## Dockerfile Template

```dockerfile
FROM python:3.11-slim
ENV TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Optional system packages
# RUN apt-get update && apt-get install -y --no-install-recommends iproute2 iptables sudo tini

ARG APP_USER=app_user
RUN useradd -ms /bin/bash ${APP_USER} && \
    echo "${APP_USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    fastapi uvicorn psutil ruamel.yaml

# --- Core + interface + adapter + config
COPY container_control_core.py .
COPY app_adapter.py .
COPY my_adapter.py .
COPY config.yaml .

# --- Your actual application source/binaries
COPY . .

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

- Kubernetes readiness probe → `/api/health`
- Horizontal scaling: watch `cpu_percent` from `/api/metrics`.
- Security: isolate privileged networking in `pre_start_hooks`; main workload runs as `app_user`.
- Upgrading: replace `container_control_core.py` in the image; adapters remain unchanged unless new hooks are desired.

Happy Showrunning! :clapper:

