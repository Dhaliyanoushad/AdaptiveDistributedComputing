# Adaptive Distributed Computing Framework for Heterogeneous Devices

Final-year project exploring how heterogeneous devices can share computing work through a central coordinator. Phase 3 adds distributed JPG/PNG processing over HTTP to the existing registration, dummy-task queue and static round-robin assignment. See [Phase 3 setup and testing](docs/phase3.md).

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

No adaptive scheduling, heartbeat, fault recovery or frontend UI is implemented. No database or machine learning was added.

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

The worker prints its registration result and stays running to poll and simulate dummy tasks. Press Ctrl+C to stop it (exit 0); registration or communication failure exits 1. Every request has a 3.05-second connection timeout and a 10-second read timeout. There is no retry or heartbeat. Without environment variables, `MASTER_URL` defaults to `http://127.0.0.1:8000` and `WORKER_ID` defaults to the local hostname. `.env` files are not loaded automatically. `POLL_INTERVAL` defaults to 1 second; `TASK_DELAY` defaults to 0.5 seconds.

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

All worker/task state resets when the master restarts. Run a single Uvicorn process without `--workers` or `--reload`; separate processes have separate dictionaries. Reusing an ID while the master is running returns HTTP 409; worker reconnection is not supported. A listed worker is only a registration record, not proof that the device is online. Stopped workers are not removed, and their assigned/running tasks are not recovered.

## Run automated tests (CMD)

```bat
master\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_master*.py" -v
worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -v
```

The environments remain separate. Master tests use the ASGI interface and Python's standard library; worker tests mock HTTP requests. No additional test dependencies are required.
