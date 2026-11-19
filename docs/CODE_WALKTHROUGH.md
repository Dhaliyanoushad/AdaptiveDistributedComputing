# Code walkthrough for students

This is a reading guide to the implemented Phases 1–9, not evidence of manual testing. Start with README.md for exact Windows CMD setup and docs/API_REFERENCE.md for request schemas.

## 1. What the project does

A user sends images to one Master. Registered Workers receive independent Tasks, process image bytes and return PNG results. A browser displays real public state. The system uses HTTP, a read-only WebSocket and Python memory; it has no database or ML.

## 2. Folder map

| Folder | Responsibility |
| --- | --- |
| master/ | FastAPI routes, image validation, registry, queue, scheduling and recovery |
| worker/ | HTTP client, independent heartbeat thread, psutil metrics and OpenCV operations |
| frontend/src/ | React dashboard, upload validation, HTTP helpers and live subscription |
| benchmarks/ | Seeded image workloads, HTTP trials, measurement formulas and reports |
| tests/ | Python behavior, concurrency, integration and setup contracts |
| scripts/ | Repository-relative CMD wrappers, inert configuration loader and verification runner |
| docs/ | Architecture, API, phase records, setup, tests and evaluation instructions |
| test_images/, uploads/, outputs/ | Ignored local data, transfers, outputs and verification evidence |

Master and Worker have separate requirements.txt and .venv directories. node_modules and frontend/dist are generated. Never commit these, .env, tokens or private data.

## 3. Which files to read first

Read README.md, master/models.py, master/main.py:create_app, worker/worker.py:main, frontend/src/App.tsx, then master/task_store.py:TaskStore. Follow a single image through image_routes.py and image_processing.py before reading scheduling and recovery. Tests are runnable examples, not experimental benchmark data.

## 4. Starting the processes

scripts/start_master.cmd invokes scripts/launch.py, which loads inert KEY=value data and builds a single Uvicorn command for master.main:app. create_app creates a private TaskStore and installs HTTP/image/dashboard routes and a lifespan-owned timeout loop.

scripts/start_worker.cmd starts worker/worker.py:main. It registers with session-v1, keeps its session private, starts HeartbeatSender and enters run_worker. scripts/start_frontend.cmd starts the existing Vite app. Wrappers resolve the repository path; terminal variables take precedence over .env. --check validates configuration without opening a service. Use separate terminals and unique WORKER_ID values.

## 5. Frontend responsibilities

App.tsx owns navigation, search, filters and selected Task ID. The six existing destinations remain: Dashboard, Process Images, Workers, Tasks, Results and Scheduling. TaskTable renders the filtered registry; it never assigns work.

DashboardPanels.tsx contains WorkerCard, TaskDetail, ResultCard and SchedulingPanel. ui.ts contains display labels, task-state descriptions, retry explanations and counts. Display names such as Gaussian Blur do not rename the API value gaussian_blur. types.ts describes the public snapshot; it contains no Worker credentials.

## 6. Uploading images

UploadPanel.tsx:validateSelection checks count, type, bytes and selected parameters. validateDimensions decodes browser images and releases object URLs even on failure. operationParameters sends only the fields for the selected operation. handleSubmit shows submission activity, calls api.ts:uploadImages and exposes the returned Task IDs.

The request is POST /images/tasks with multipart files, operation and a JSON string params. For example, resize uses {"width":640,"height":480}. Each of 1–20 JPG/PNG inputs is limited to 10 MiB, 4096 pixels per side and 16 million pixels. Submission means accepted/queued, not completed. The Master validates again; browser validation is not a security boundary.

## 7. Images become Tasks

master/image_routes.py:image_router installs upload/transfer/result endpoints. parameters validates operation-specific fields; read_image and master/image_files.py:inspect_image inspect real bytes. save_unique creates server-generated names in approved directories. A complete valid batch is published through TaskStore.submit_images; failed uploads do not leave a partial task batch.

TaskStore.submit gives each Task a UUID, timestamps and pending state, then appends its ID to the FIFO. Paths stay on the Master. Public Tasks expose operation, payload, state, assigned_worker, attempt_count and attempt_history.

## 8. Assignment and Static Scheduling

TaskStore._distribute runs under the store RLock. Static Scheduling rotates through registration order, skipping offline or busy Workers. Each Worker holds at most one active Task. A pending Task becomes assigned and gets a new private assignment token. poll/poll_assignment deliver it once; simultaneous polls cannot claim the same assignment twice. Retried work requires a modern session-aware Worker.

## 9. Adaptive Scheduling

master/scheduling.py:SchedulerSettings reads the existing SCHEDULER_MODE and score configuration. Static remains default. resource_score combines CPU headroom, RAM headroom, available RAM, active load and processing history. TaskStore._distribute enforces freshness, minimum RAM, eligibility, tie order, fallback and bounded fairness before choosing.

Weights remain CPU .35, RAM .20, available RAM .15, load .15 and history .15 by default. Idle candidates currently have zero active load; one-active-task eligibility still applies. Missing/stale metrics use the existing round-robin fallback; fresh but insufficient RAM may leave work pending. Running work is not migrated. The dashboard shows configuration and actual reasons; it cannot switch mode at runtime. Adaptive Scheduling is not a promise of speedup.

## 10. Processing and returning image bytes

worker/worker.py:execute_image downloads GET /tasks/{task_id}/input over HTTP using Worker/session/assignment identity. worker/image_processing.py:process_image translates OpenCV failures into the existing ValueError. Its helpers _decode_image, _apply_operation and _encode_png separate validation, transformation and encoding.

The four operations remain cvtColor(BGR2GRAY), resize(INTER_AREA), GaussianBlur and grayscale Canny. All output is PNG. The Worker POSTs bytes to /tasks/{task_id}/result. It does not open a Master path. Dummy tasks still use their original delay/start/complete path.

TaskStore.accept_result validates ownership, session, current assignment, running state and decoded output before publication. result_path serves only accepted completed results. ResultCard previews /result and links /result/download; Worker-only originals are never exposed in the gallery.

## 11. Task states and updates

pending → assigned → running → completed is the normal path. Failed attempts may return the same Task ID to pending or end in failed. TaskStore.update validates start/complete/fail transitions. Duplicate accepted completion is idempotent; the image route cannot be bypassed using dummy completion. Search/filter values remain pending, assigned, running, completed and failed.

TaskDetail fetches /tasks/{task_id}/attempts. It shows Worker, count, dates, error, original reason, score and each attempt. A recorded retry means a retry was requested, not proof a new Worker started or finished it. Always read the latest Task state.

## 12. Heartbeats and metrics

worker/monitoring.py:collect_metrics calls psutil without a blocking CPU sample. Missing samples remain null. HeartbeatSender sends periodically in an independent thread, normally every 3 seconds, including during processing. Requests have timeouts and a bounded wait avoids a tight failure loop.

TaskStore.heartbeat validates current session identity, records Master UTC last_seen and uses monotonic receipt time for liveness. master/monitoring.py:timeout_loop periodically invokes recover_timeouts (normally every second). A Worker is offline when elapsed receipt time exceeds WORKER_TIMEOUT (normally 10 seconds); GET /workers is not required. Lifespan cancellation cleans up the sweep.

## 13. Fault recovery, retries and stale results

TaskStore.expire_workers detects timeout. _retry_or_fail releases the active slot, records the outcome and queues the same Task at the FIFO tail for an eligible modern attempt, within MAX_TASK_ATTEMPTS (normally 3). Explicit retryable failures follow the same budget. Permanent failures or exhausted budgets end failed. Original image input remains for another attempt.

An offline modern Worker may register again with the same ID and a new session. An online duplicate receives 409. Legacy identities cannot securely reconnect/retry. authorize checks the current session, assignment session and per-attempt token; an old Worker or delayed result cannot finish or replace a newer attempt. This is fencing on a trusted LAN, not authenticated initial enrollment or TLS. Heartbeating but hung work has no separate execution deadline. Master restart loses registry, queue, attempts and sessions; files do not restore metadata.

## 14. Live dashboard updates

master/dashboard.py:public_snapshot copies public state while holding the lock. stream_dashboard releases it before JSON encoding/network sends, validates Origin and sends changed snapshots on the bounded loop. Worker credentials are excluded.

frontend/src/useLiveDashboard.ts opens /ws/dashboard. It retains real last-known data on errors, reconnects with bounded exponential backoff and uses periodic HTTP polling while disconnected. It avoids overlapping polls and cleans up timers/sockets on unmount. Phase 9 did not alter this transport logic. Connection errors are visible; missing data is never replaced by fake statistics.

## 15. Benchmarking and reports

benchmarks/workload.py:generate creates seeded, fingerprinted workloads; inspect_workload validates manifests. runner.py:run_trial uses the real HTTP task protocol and verifies topology. Run single-device, static and adaptive trials on matching inputs, operation, environment and stable Worker sets; warmups are retained but excluded from comparisons.

metrics.py:summarize_tasks calculates completed images / elapsed seconds. aggregate uses valid matched repeated trials: speedup is baseline mean time / distributed mean time; efficiency is speedup / allocated Worker count. It requires at least three valid measured trials and rejects contaminated comparisons. Failed/partial observations remain evidence. report.py:build_report exports JSON/CSV/Markdown/SVG with missing comparisons labeled unavailable.

There is no benchmark results API or benchmark dashboard page. Scheduling contains explanatory guidance; use the existing scripts/benchmark_*.cmd wrappers and docs/phase7.md for real reports. Never use test fixtures as performance evidence.

## 16. Automated verification and manual acceptance

From repository Windows CMD, run scripts\test_all.cmd. It executes Master, Worker, benchmark, frontend and setup suites, production build, pip checks and launcher checks. It retains actual stage logs under ignored outputs/verification/UUID. See AUTOMATED_TESTS.md for separate commands and TEST_RESULTS.md for actual counts.

Master tests use the socket-free test runner and invoke real Worker OpenCV subprocesses for HTTP/ASGI image round trips. This does not prove live TCP, browser rendering or two-laptop LAN operation. Follow TESTING_GUIDE.md and TWO_LAPTOP_SETUP.md later; all new manual cases remain NOT YET EXECUTED. WinError 10013, development npm advisories, clean-machine install, browser/LAN acceptance and real benchmarks remain open.
