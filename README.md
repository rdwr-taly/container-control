# Container Control

**One immutable core + lightweight adapter = zero boilerplate.**

This repository explains how to integrate any containerised workload with
Showrunner using the **Container Control Core (CCC)**.

---

## Contents

1. [Concept](#concept)  
2. [Files you care about](#files-you-care-about)  
3. [Building an adapter](#building-an-adapter)  
4. [Configuration (`config.yaml`)](#configuration-configyaml)  
5. [Dockerfile template](#dockerfile-template)  
6. [API reference](#api-reference)  
7. [Operational tips](#operational-tips)

---

## Concept

markdown
Copy
Edit
       (root, FastAPI)
┌──────────────────────────────────────────┐
│ container_control_core.py │
│ • HTTP API (/api/*, /metrics) │
│ • lifecycle / state / signals │
│ • container-level metrics │
│ • privilege separation helper │
└──────────────┬───────────────────────────┘
│ imports adapter class
▼
app_adapter.py ← common interface
│ subclassed by you
▼
my_adapter.py ← 15-40 loc typical
│ calls
▼
Your real workload (async code, binary, …)

yaml
Copy
Edit

*All containers share the **exact same** `container_control_core.py`;  
only `my_adapter.py` and `config.yaml` vary per application.*

---

## Files you care about

| File                       | Keep unmodified? | Purpose |
|----------------------------|------------------|---------|
| `container_control_core.py`| **Yes**          | FastAPI service, new `/api/update` included. |
| `app_adapter.py`           | **Yes**          | Abstract base class, defines contract. |
| `my_adapter.py`            | No               | Your shim – implements the contract. |
| `config.yaml`              | No               | Declares which adapter to load & options. |
| `Dockerfile`               | No               | Builds the image using the template below. |

---

## Building an adapter

1. **Copy** `app_adapter.py` into your repo.  
2. **Create** `my_adapter.py`:

```python
from __future__ import annotations
import subprocess, threading
from app_adapter import ApplicationAdapter

class MyAdapter(ApplicationAdapter):
    def start(self, payload, *, ensure_user):
        cmd = ["python3", "my_tool.py", "--flows", payload["flowfile"]]
        self.proc = subprocess.Popen(ensure_user(cmd))
        return self.proc                    # opaque handle

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=5)

    def update(self, payload):
        # Example live tweak: change log-level without restart
        level = payload.get("log_level")
        if level is None:
            return False
        subprocess.run(["kill", "-USR1", str(self.proc.pid)])  # hypothetical
        return True

    def get_metrics(self):
        return {"running": self.proc.poll() is None}
Add any privileged setup:

python
Copy
Edit
    def pre_start_hooks(self, payload):
        # root tc shaping
        bw = payload.get("bandwidth", 20)
        subprocess.run(["tc", "qdisc", "add", "dev", "eth0", "root",
                        "tbf", "rate", f"{bw}mbit", "latency", "50ms",
                        "burst", "32k"], check=True)
Done. Typical adapter size: < 40 lines.

Configuration (config.yaml)
yaml
Copy
Edit
adapter:
  class: my_adapter.MyAdapter          # dotted-path import
  primary_payload_key: flowfile        # key that must exist in /api/start body
  run_as_user: app_user                # null ⇒ run as root
If your workload never needs privilege-drop, omit run_as_user.

Dockerfile template
dockerfile
Copy
Edit
FROM python:3.11-slim
ENV TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Optional system packages (sudo, tc, etc.)
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
API reference
Method	Path	Description
POST	/api/start	Start the workload (or restart if running). Payload must include primary key named in config.yaml.
POST	/api/update	Live config tweak. Adapter decides what keys it understands. Returns 200 on success, 409 if unsupported, 400 if app not running.
POST	/api/stop	Graceful stop.
GET	/api/metrics	JSON with container + adapter metrics.
GET	/metrics	Prometheus exposition.
GET	/api/health	Simple liveness check.

All timestamps are UTC ISO-8601 (YYYY-MM-DDTHH:MM:SS.mmmmmmZ).

Operational tips
Kubernetes readiness probe → /api/health

Horizontal scaling – external orchestrator can watch cpu_percent from /api/metrics.

Security – isolate privileged networking in pre_start_hooks; main workload runs as app_user.

Upgrading – replace container_control_core.py in the image; adapters remain unchanged unless new hooks are desired.

Happy Showrunning! 🎬

markdown
Copy
Edit

These artefacts give you everything required to:

1. Embed the **new live-update capability** into *any* container,  
2. Keep the core identical across **all** applications, and  
3. Provide crystal-clear docs for fellow developers.
