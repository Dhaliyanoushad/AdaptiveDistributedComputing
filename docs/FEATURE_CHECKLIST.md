# Feature preservation map — Phase 9

Source links and test names refer to real repository files. Automated evidence is in TEST_RESULTS.md; manual acceptance is NOT YET EXECUTED. Passing regressions establish tested behavior, not proof for every possible input or hardware environment.

| Implemented feature | Source | Automated evidence |
| --- | --- | --- |
| Health, registration, duplicate IDs, listing/logging/validation | master/main.py, models.py; worker/worker.py:main | test_master.py; test_worker.py |
| CPU/RAM/available RAM, metric failures and independent heartbeats | worker/monitoring.py:collect_metrics, HeartbeatSender | test_worker_monitoring.py |
| Periodic offline detection, clocks, lifecycle cleanup | master/monitoring.py; task_store.py:expire_workers | test_master_monitoring.py |
| Offline modern reconnect, online duplicate protection, session fencing | task_store.py:register, authorize | test_master_monitoring.py; test_master_phase5.py |
| Dummy queue, unique IDs/states/timestamps, polling/start/complete/fail | task_store.py:submit, poll, update; worker.py:run_worker | test_master_tasks.py; test_worker_tasks.py |
| Atomic ownership, one active Task, duplicate claim/completion protection | task_store.py:_lock, _active, _delivered, update | test_master_tasks.py; test_master_phase5.py |
| Multi-image atomic batch, byte/type/size/parameter/path validation | image_routes.py; image_files.py; UploadPanel.tsx | test_master_images.py; UploadPanel.test.tsx |
| Grayscale, Resize, Gaussian Blur, Edge Detection, JPEG input, PNG output | worker/image_processing.py:process_image and three helpers | test_worker_images.py (exact OpenCV pixel comparisons and validation boundaries) |
| Actual HTTP byte protocol, result validation, previews/downloads | image_routes.py; task_store.py:accept_result; worker.py:execute_image | test_master_images.py (ASGI + Worker processor subprocess); test_worker_images.py; api.test.ts; App.test.tsx |
| Static round-robin, registration order/cursor, busy/offline exclusion | task_store.py:_distribute | test_master_tasks.py; test_master_phase5.py |
| Adaptive CPU/RAM/available RAM/load/history scores, minimum RAM | scheduling.py:resource_score; task_store.py:_distribute | test_master_phase5.py |
| Eligibility, fairness, tie order, missing/stale fallback, no migration | task_store.py:_distribute | test_master_phase5.py |
| Timeout/retryable failure recovery, FIFO requeue, input retained | task_store.py:recover_timeouts, _retry_or_fail | test_master_phase5.py; test_worker_phase5.py |
| Retry limits, permanent failure, stale-result and assignment fencing | task_store.py:authorize, update, accept_result | test_master_phase5.py; test_master_images.py; test_worker_phase5.py |
| Dashboard counts and all six destinations | App.tsx | App.test.tsx (original overview + new navigation cases) |
| Worker metric bars, active load, last heartbeat, missing/stale labels | DashboardPanels.tsx:WorkerCard | App.test.tsx (old nullable/stale and new labels/load cases) |
| Upload instructions/descriptions, selected parameters, activity/IDs | UploadPanel.tsx:handleSubmit, operationParameters | UploadPanel.test.tsx (validation, real File payloads, progress and schema assertions) |
| All five states, search/filter, reassignment, errors and attempt reasons | App.tsx:TaskTable; DashboardPanels.tsx:TaskDetail; ui.ts | App.test.tsx |
| Results gallery, preview errors and original-input restriction | App.tsx; DashboardPanels.tsx:ResultCard; api.ts | App.test.tsx; api.test.ts; test_master_images.py |
| Read-only mode/config/load/history/retry guidance | DashboardPanels.tsx:SchedulingPanel | App.test.tsx |
| Changed public snapshots, CORS, Origin and credential privacy | master/dashboard.py | test_master_dashboard.py; test_master_integration.py |
| WebSocket reconnect, backoff, HTTP fallback and cleanup | useLiveDashboard.ts | useLiveDashboard.test.tsx |
| Responsive layout, focus indicators, keyboard-scrollable task table | styles.css; App.tsx:TaskTable | Production build checks CSS/TS; actual browser/mobile/accessibility acceptance pending P9-09/10 |
| Seeded workloads/manifests and reproducibility | benchmarks/workload.py | test_benchmarks.py |
| Single/static/adaptive, topology, repeated trials/warmups/failures | benchmarks/runner.py | test_benchmarks.py |
| Throughput, valid speedup/efficiency, invalid/partial observations | benchmarks/metrics.py | test_benchmarks.py |
| CSV/JSON, Markdown/SVG reports, metadata/utilization | benchmarks/report.py | test_benchmarks.py |
| Standalone report explanations; no invented data or runtime API | DashboardPanels.tsx:BenchmarkHelp | App.test.tsx (descriptions/limitations); reports remain external files |
| CMD setup/start/test/benchmark wrappers, inert .env, localhost | scripts/*.cmd; scripts/launch.py, verify.py | test_integration_setup.py; non-serving launcher checks |
| Existing HTTP paths, task states/operations, multipart schema, identity headers | master/main.py, models.py, image_routes.py | test_master_integration.py including new exact contract assertions; api.test.ts |
| LAN instructions, real browser, installation and hardware experiments | README.md; TWO_LAPTOP_SETUP.md; TESTING_GUIDE.md; phase7.md | Procedures exist; NOT YET EXECUTED in Phase 9 |

## Change boundary checked

- Master scheduling, queue, recovery, HTTP routes, models and security implementation are unchanged in Phase 9.
- Worker HTTP/heartbeat code is unchanged. Only image pipeline helpers were extracted, preserving validation order, limits, errors and OpenCV operations.
- Benchmark code/formulas, frontend api.ts/useLiveDashboard.ts and CMD scripts/configuration are unchanged.
- All existing tests remain. One frontend exact-label assertion now expects Adaptive Scheduling; new tests add coverage instead of removing assertions.
- No dependencies, frameworks, endpoints, runtime mode controls or fake benchmark charts were added.
- Historical Phase 1–8 manual instructions and evidence remain. Current navigation labels are mapped in the Phase 9 testing section.
