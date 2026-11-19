# Adaptive Distributed Computing Framework for Heterogeneous Devices

Final-year project coordinating Python workers through a FastAPI master to process images across heterogeneous devices. Phases 1–8 implement communication, image tasks, monitoring, static/adaptive scheduling, bounded recovery, a React dashboard, benchmark tools and a documented handoff. **Implementation completion is not manual validation:** browser, LAN and actual performance experiments remain pending.

## Documentation entry points

- [Manual testing guide](docs/TESTING_GUIDE.md) and [execution template](docs/TEST_EXECUTION_TEMPLATE.md)
- [Two-laptop setup](docs/TWO_LAPTOP_SETUP.md)
- [Architecture](docs/ARCHITECTURE.md), [API reference](docs/API_REFERENCE.md)
- [Automated suites](docs/AUTOMATED_TESTS.md), [actual results](docs/TEST_RESULTS.md)
- [Demo sequence](docs/DEMO_GUIDE.md), [final checklist](docs/FINAL_CHECKLIST.md)

## Components and features

`master/` owns the locked in-memory registry, FIFO, scheduler, attempts and result validation. `worker/` sends independent psutil heartbeats, polls fenced assignments, downloads image bytes, runs OpenCV and uploads PNGs. `frontend/` displays public data through read-only WebSockets with polling fallback. `benchmarks/` runs isolated real-image HTTP trials and exports recorded observations; it never changes master mode or fabricates results.

Operations: grayscale, exact resize, Gaussian blur and Canny edges. JPG/PNG inputs become PNG outputs with unique server-generated filenames. Dummy tasks remain for tests. Modern session and assignment tokens prevent stale result publication. Static mode is default; adaptive mode uses configurable resource scores and fairness without ML. Timeout/transient failures retry within MAX_TASK_ATTEMPTS (default 3). Old results cannot overwrite accepted output.

Stack: Python 3.13, FastAPI/Uvicorn/Pydantic, requests, psutil, OpenCV-headless/Pillow/NumPy, HTTP/WS, React/Vite/TypeScript/Tailwind. No database, broker, ML, Spark or Kubernetes. One master process only; restart loses all metadata, queue, history and credentials. Disk files remain but are not rediscovered.

## Windows 10/11 installation — CMD

Open Command Prompt in the repository (Explorer address bar: type cmd). All commands are relative to the repository, not a specific username.

```bat
python --version
node --version
npm --version
git --version
scripts\setup.cmd
```

Tested baseline: Python 3.13.2, Node 22.14.0, npm 11.12.0, Git 2.46.0. Setup requires Python 3.13 and Node >=22.14. It creates missing separate virtual environments, installs each requirements.txt and runs npm ci against the frontend lockfile. Fresh installation requires package-index access. It never replaces existing .env configuration, changes firewall settings or installs services. Address the first setup error before running the application.

Optional configuration:

```bat
if not exist master\.env copy master\.env.example master\.env
if not exist worker\.env copy worker\.env.example worker\.env
if not exist frontend\.env copy frontend\.env.example frontend\.env
```

Wrappers load simple KEY=value configuration as inert data, with existing terminal variables taking precedence. No shell evaluation/interpolation is performed. Direct uvicorn/worker.py commands do not automatically load .env files. Vite variables are public; never store credentials in them. Session/attempt tokens are generated dynamically, not configured in files.

## Local startup — four separate CMD terminals

Master:

```bat
scripts\start_master.cmd
```

Worker 1:

```bat
set "WORKER_ID=worker-1"
scripts\start_worker.cmd
```

Worker 2:

```bat
set "WORKER_ID=worker-2"
scripts\start_worker.cmd
```

Frontend:

```bat
scripts\start_frontend.cmd
```

Open http://127.0.0.1:5173 (dashboard), http://127.0.0.1:8000/docs (Swagger), http://127.0.0.1:8000/health. Wrappers resolve their repository directory even when invoked from elsewhere. Each accepts --check for non-serving path/host/port/URL checks and --env-file for an explicit alternate file. Full application parameter validation still occurs at startup; --check is not a service readiness test. Stop owned processes with Ctrl+C, workers before master. Never use multiple master processes or reload with this in-memory registry.

Upload images in the dashboard, choose operation/parameters, track returned task IDs and inspect history/results. Upload success means queued, not completed. The browser never holds worker tokens; original inputs remain restricted to assigned workers. API limits: 1–20 files/batch, 10 MiB each, 4096 pixels/side, 16 million pixels. See API reference for exact schemas.

## Configuration and LAN

Set SCHEDULER_MODE=adaptive in the master terminal before startup to change from static round-robin. No runtime mode toggle exists. [phase5.md](docs/phase5.md) describes scores, weights, fallback and fairness. Default worker heartbeats wait 3 seconds with 2-second connect/read timeouts; master timeout is 10 seconds with 1-second checks. Task HTTP timeouts remain connect 3.05/read 10 seconds. Worker defaults: MASTER_URL=http://127.0.0.1:8000, WORKER_ID=hostname, POLL_INTERVAL=1, TASK_DELAY=.5 for dummy tasks only.

For LAN, set MASTER_HOST=0.0.0.0 on Laptop A and actual MASTER_URL=http://LAPTOP_A_IPV4:8000 on Laptop B. Set VITE_MASTER_URL and CORS_ALLOWED_ORIGINS to the actual reachable API and browser origin. Required ports are 8000 (master HTTP/WS) and 5173 (dashboard dev server). Permit only intended apps/ports on a trusted Private network. Never disable the firewall automatically or expose this prototype publicly. [TWO_LAPTOP_SETUP.md](docs/TWO_LAPTOP_SETUP.md) has exact commands and troubleshooting.

## Automated verification

```bat
scripts\test_all.cmd
```

Runs every master/worker/benchmark/frontend/setup suite, production build, dependency and launcher checks. It continues after stage failures, returns nonzero on any failure and retains logs under ignored outputs/verification/UUID/. It uses the existing socket-free master ASGI runner: a pass is not live TCP/browser/LAN validation. [TEST_RESULTS.md](docs/TEST_RESULTS.md) contains actual observed counts. Review logs before sharing; do not commit private data.

## Benchmarking

```bat
scripts\benchmark_prepare.cmd --directory benchmarks\workloads\small-42 --profile small --seed 42
copy benchmarks\environment.example.json benchmarks\environment.json
```

Fill all metadata placeholders. With an isolated static master and exactly one online worker bench-1:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.runner --mode single --workers bench-1 --workload benchmarks\workloads\small-42 --operation grayscale --environment benchmarks\environment.json --trials 3 --warmups 1
```

Restart isolated master/workers for static/adaptive modes with the same two-worker pool, workload and metadata. Generate reports:

```bat
scripts\benchmark_report.cmd --source benchmarks\results --output benchmarks\reports\experiment-01
```

[phase7.md](docs/phase7.md) defines timing/throughput/speedup/efficiency, warmups and invalid trials. Generated datasets/reports are ignored. No actual performance experiment or speedup is claimed during implementation.

## Limitations and open issues

- Socket diagnostics: loopback bind/listen succeeded on ephemeral/8000/5173, but ephemeral connect failed WinError 10013; socketpair stalled and DNS failed. This points to execution-context restrictions, not a conflict on application ports. Exact policy/product cause is undetermined. Run python scripts\diagnose_network.py; no system security settings were changed.
- Full npm audit still reports 1 moderate and 2 critical development-tool findings. Production-only audit reports zero. Compatible Vitest update attempts are blocked by registry DNS ENOTFOUND. Update and rerun tests/build/audit with network access; do not blindly force upgrades.
- Trusted-LAN prototype: no authenticated enrollment/TLS, persistence, storage quotas or retention service. Legacy static workers cannot reconnect or receive secure retries. Structural output validation is not proof of work by an untrusted worker. No independent deadline exists for a heartbeating-but-hung task.
- Multipart parsing can spool uploads before endpoint limits. Whole-host metrics/history and UI polling are not performance proof. OS/DNS stalls can exceed nominal HTTP timeouts.
- Manual/real-browser/LAN/performance acceptance remains for the teammate. Phase 8 completes implementation/handoff, not manual validation. There is no separate phase4.md; its implementation records remain in the testing documents and Git history.
