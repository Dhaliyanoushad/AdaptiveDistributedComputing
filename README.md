# Adaptive Distributed Computing Framework for Heterogeneous Devices

Final-year project exploring how heterogeneous devices can share computing work through a central coordinator. This repository currently contains the initial project scaffold and dependency declarations only.

## Planned architecture

- **Master:** Python and FastAPI; future HTTP/WebSocket interfaces, worker registry and an in-memory task queue.
- **Workers:** Python, requests, psutil and OpenCV for future device reporting and image tasks.
- **Frontend:** React, Vite and Tailwind CSS, to be initialized during the dashboard phase.
- **Communication:** HTTP and WebSockets, to be implemented incrementally.
- **Storage:** No database initially. No machine learning initially.

OpenCV uses the headless distribution because workers do not initially need desktop display windows. It provides the `cv2` import; do not install it alongside another OpenCV distribution in the same environment.

## Project layout

```text
master/       Master dependencies and future coordinator code
worker/       Worker dependencies and future device code
frontend/     Reserved for React + Vite + Tailwind
tests/        Future automated tests
docs/         Design notes and environment verification
test_images/  Local input images (ignored by Git)
outputs/      Generated results (ignored by Git)
```

## Windows setup

Run from the repository root using Python 3.13:

```powershell
python -m venv master/.venv
python -m venv worker/.venv
& .\master\.venv\Scripts\python.exe -m pip install -r master/requirements.txt
& .\worker\.venv\Scripts\python.exe -m pip install -r worker/requirements.txt
```

Activate one environment per terminal:

```powershell
# Master terminal
.\master\.venv\Scripts\Activate.ps1

# Worker terminal (separate terminal)
.\worker\.venv\Scripts\Activate.ps1
```

Run `deactivate` to leave an environment. If PowerShell blocks activation, use the environment's Python executable directly as above; activation is optional. In Command Prompt use `master\.venv\Scripts\activate.bat` or `worker\.venv\Scripts\activate.bat`.

Dependency files specify bounded version ranges; they are not reproducible lockfiles. See `docs/environment-checks.md` for the actual installation and verification results from initialization.

## Planned development phases

1. **Foundation (current):** directory scaffold, isolated environments, dependencies, conventions and environment checks.
2. **Connectivity:** minimal master API and worker registration; establish HTTP/WebSocket contracts.
3. **Liveness:** worker heartbeat and disconnect handling.
4. **Task execution:** in-memory queue and a small image-processing task with result collection.
5. **Scheduling:** start with a simple baseline, then adapt allocation using device capability and load; compare against the baseline.
6. **Dashboard:** initialize React + Vite + Tailwind and expose system state through a minimal UI.
7. **Evaluation:** heterogeneous-device experiments, failure tests, performance measurements and final documentation.

No master-worker communication, task processing, scheduling, heartbeat or frontend UI is implemented in this phase. There is no application entry point to run yet.
