# Adaptive Distributed Computing Framework for Heterogeneous Devices

Final-year project exploring how heterogeneous devices can share computing work through a central coordinator. Phase 3 adds distributed JPG/PNG processing over HTTP to the existing registration, dummy-task queue and static round-robin assignment. See [Phase 3 setup and testing](docs/phase3.md).

Phase 4 adds CPU/RAM monitoring, independent heartbeats, online/offline detection and session-protected reconnection. See [the Phase 4 manual cases](docs/TESTING_GUIDE.md#8-phase-4-resource-monitoring-and-heartbeats--not-yet-executed), [automated suites](docs/AUTOMATED_TESTS.md) and [actual results](docs/TEST_RESULTS.md).

Phase 5 adds selectable rule-based adaptive scheduling and bounded fault recovery. [Phase 5 policy and configuration](docs/phase5.md) supersedes historical statements below that task recovery is unavailable. Static remains the default. New assignments have generation tokens; updated workers send them automatically. No adaptive speedup is claimed.

To select a mode, set `SCHEDULER_MODE=static` or `SCHEDULER_MODE=adaptive` in the master CMD before startup. `MAX_TASK_ATTEMPTS` defaults to 3. Inspect `GET /scheduler` and `/tasks/{task_id}/attempts` to review decisions and retries. Recoverable modern-worker tasks are now requeued after heartbeat timeout; permanent failures and exhausted attempts become terminal. Legacy clients cannot receive retries. All metadata still disappears on master restart. See the Phase 5 guide for all weight/freshness/fairness defaults and the updated teammate guide for exact commands.

## Planned architecture

- **Master:** Python and FastAPI; HTTP worker registration, task inspection, an in-memory FIFO queue and static round-robin assignment. WebSockets remain future work.
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
tests/        Master endpoint and worker client tests
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

1. **Foundation (complete):** directory scaffold, isolated environments, dependencies, conventions and environment checks.
2. **Phase 1 — Connectivity (implemented):** minimal master HTTP API and worker registration. WebSockets remain future work.
3. **Phase 2 - Tasks and static distribution (implemented):** in-memory dummy-task registry/queue, round-robin assignment, polling and task-state updates.
4. **Phase 3 - Distributed image processing (implemented):** grayscale, resize, Gaussian blur and edge detection; input/result HTTP byte transfers. Liveness and recovery remain future work.
5. **Scheduling:** start with a simple baseline, then adapt allocation using device capability and load; compare against the baseline.
6. **Dashboard:** initialize React + Vite + Tailwind and expose system state through a minimal UI.
7. **Evaluation:** heterogeneous-device experiments, failure tests, performance measurements and final documentation.

Static/adaptive scheduling, bounded task recovery and the local React dashboard are implemented. No database or machine learning was added.

## Phase 6 dashboard

The React/Vite/TypeScript/Tailwind dashboard is implemented locally. It displays actual API data for overview, uploads, workers, task history, completed results and scheduling. This section supersedes historical roadmap statements above that the frontend is future work. No benchmarking or Phase 7 features were added.

Install and start from Windows CMD:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing\frontend
npm install
set "VITE_MASTER_URL=http://127.0.0.1:8000"
npm run dev
```

Open `http://127.0.0.1:5173`. Start the master and workers in separate terminals using the existing commands below. The dev server binds to loopback and requires port 5173 rather than silently changing ports. `frontend/.env.example` documents the optional Vite setting; `.env` is ignored. Vite variables are public build configuration, never secrets.

The master defaults `CORS_ALLOWED_ORIGINS` to `http://127.0.0.1:5173,http://localhost:5173`. Override with a comma-separated explicit HTTP(S) origin list before master startup; wildcards, paths and credentials are rejected. The same origin policy protects `WS /ws/dashboard`. Snapshots include only public workers/tasks/scheduler data, sent on changes with approximately two-second checks; task processing never waits for clients. The frontend initially fetches existing endpoints, reconnects WebSockets with 1/2/4/8/16/30-second backoff and polls every five seconds while disconnected. Failed refreshes retain the last snapshot with an error notice. There is no runtime scheduling-mode toggle.

Verification commands (frontend directory):

```bat
npm test
npm run build
npm audit
```

Tests and build are recorded in [TEST_RESULTS.md](docs/TEST_RESULTS.md). **Unresolved development-tool audit findings:** the installed Vitest dependency tree reports 1 moderate and 2 critical advisories. A patched-version upgrade attempt failed with npm registry DNS `ENOTFOUND`; it was not applied. Review/update compatible test tooling and rerun tests/build/audit when registry access is available. Do not expose test tooling on a public network. Detailed local/LAN/manual cases are in [TESTING_GUIDE.md](docs/TESTING_GUIDE.md).

## Run the master and workers on Windows CMD

Open two Command Prompt terminals. These commands use each existing virtual environment directly; activation is optional.

Terminal 1 — master:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 — worker:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=local-worker-1"
worker\.venv\Scripts\python.exe worker\worker.py
echo %ERRORLEVEL%
```

The worker prints its registration result and stays running to poll and process tasks. Press Ctrl+C to stop it (exit 0); registration or task communication failure exits 1. Task requests have a 3.05-second connection timeout and a 10-second read timeout. Heartbeats use their own thread and timeout settings below. There is no task retry. Without environment variables, `MASTER_URL` defaults to `http://127.0.0.1:8000` and `WORKER_ID` defaults to the local hostname. `.env` files are not loaded automatically. `POLL_INTERVAL` defaults to 1 second; `TASK_DELAY` defaults to 0.5 seconds.

Terminal 3 - second worker (keep terminal 2 running):

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=local-worker-2"
set "POLL_INTERVAL=1"
set "TASK_DELAY=3"
worker\.venv\Scripts\python.exe worker\worker.py
```

Use a unique ID for every worker process. For a reproducible equal-delay demonstration, also set `TASK_DELAY=3` in terminal 2 before launching that worker. Open `/docs`, submit a batch through **POST /tasks**, then inspect **GET /tasks**. See [the Phase 2 guide](docs/phase2.md) for exact request bodies, CMD submission commands and manual state/ownership checks.

Verify in a browser at `http://127.0.0.1:8000/workers`, or use CMD:

```bat
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8000/workers
```

Open `http://127.0.0.1:8000/docs` for Swagger UI. Expand **GET /workers**, select **Try it out**, then **Execute** to see the registry. To register through Swagger, use **POST /workers/register** with a new worker ID. See [the Phase 1 guide](docs/phase1.md) for the request contract and a later two-laptop test.

All worker/task state resets when the master restarts. Run a single Uvicorn process without `--workers` or `--reload`; separate processes have separate dictionaries. Reusing an online ID returns HTTP 409. Updated workers can reconnect after offline detection and receive a new session token. Legacy registrations cannot reconnect. An old assigned/running task is not recovered or transferred to the new session and keeps that worker ID busy. Stopped workers remain listed with offline status.

## Phase 4 configuration

Run commands remain the same. Set these in CMD before starting the corresponding process:

| Process | Variable | Default | Meaning |
| --- | --- | --- | --- |
| Master | `WORKER_TIMEOUT` | `10` | Seconds since last heartbeat receipt before offline (strictly greater than timeout) |
| Master | `TIMEOUT_CHECK_INTERVAL` | `1` | Background timeout sweep seconds |
| Worker | `HEARTBEAT_INTERVAL` | `3` | Seconds between heartbeat attempts after each request finishes |
| Worker | `HEARTBEAT_HTTP_TIMEOUT` | `2` | Connect/read timeout seconds for heartbeat HTTP calls |
| Worker | `MASTER_URL` | `http://127.0.0.1:8000` | Master base URL |
| Worker | `WORKER_ID` | local hostname | Unique worker identity |
| Worker | `POLL_INTERVAL` | `1` | Idle task polling delay seconds |
| Worker | `TASK_DELAY` | `0.5` | Dummy-task simulation seconds; not an image-processing delay |

All intervals/timeouts must be finite and positive; TASK_DELAY may be zero. Existing task HTTP timeouts remain fixed at connect 3.05/read 10 seconds. Configure WORKER_TIMEOUT comfortably above heartbeat interval plus network latency; a too-small timeout can cause false offline detection. A lifecycle background task expires workers without GET requests. A separate worker thread samples psutil with nonblocking CPU reads and sends heartbeats while tasks run. Unavailable metrics are null. Available RAM is reported in MiB (1024² bytes), under the API field `available_ram_mb`.

`GET /workers` now adds `last_seen`, `status`, `cpu_percent`, `ram_percent` and `available_ram_mb` while keeping worker_id/hostname and the array shape. `GET /workers/{worker_id}` returns one record. `POST /workers/heartbeat` accepts those metrics and worker_id; optional client timestamp is informational, never the timeout authority. Session-aware registrations send `X-Worker-Protocol: session-v1` and receive a private `X-Worker-Session` response header. Updated workers attach it to heartbeat, polling, task updates and image transfers automatically. Do not log or commit the token. Missing/stale token returns 401, unknown worker 404, offline/session-task conflict 409, invalid body 422. This is session fencing, not authenticated enrollment: legacy registrations retain the original trusted-network assumptions, cannot be upgraded/reconnected, and time out if they do not heartbeat. No automatic reconnect loop, retry or task recovery is implemented.

## Run automated tests (CMD)

```bat
master\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_master*.py" -v
worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -v
```

The environments remain separate. Master tests use the ASGI interface and Python's standard library; worker tests mock HTTP requests. No additional test dependencies are required.
