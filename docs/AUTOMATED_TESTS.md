# Automated tests: Phases 1–9

## One-command final verification

```bat
scripts\test_all.cmd
```

From repository CMD this wrapper invokes scripts/verify.py in the master environment, runs every suite, frontend build, both pip checks and three non-serving launcher checks. It continues after stage failure, returns nonzero if any failed, and retains UTF-8 logs and incremental/final results.json in ignored outputs/verification/UUID/. Console output escapes unsupported characters on older Windows encodings; raw logs preserve Unicode. Interrupted evidence has complete=false when a stage record exists; never treat it as a full pass. Installation is separate via scripts/setup.cmd; a clean-machine network installation was not rerun during handoff.

tests/test_master_integration.py has 5 HTTP/schema/header/public-data contracts and is included by master discovery. New tests/test_integration_setup.py has 7 configuration/CMD/verification tests and is a separate stage. Current counts: 81 master, 35 worker, 24 benchmark, 38 frontend, 7 setup = **185 unique methods**. Earlier inventory rows describe historical phase counts.

The encoded worker-ID polling test first reproduced a genuine 404, then verified the path-aware route fix. No scheduler/recovery algorithm changed. Actual CMD --check wrappers and benchmark --help wrappers were executed without starting services. Read-only socket probes are diagnostics, not live TCP/browser passes. See TEST_RESULTS.md for the final run and open issues.

This is the inventory and execution guide, not a test result record. See [TEST_RESULTS.md](TEST_RESULTS.md) for observed runs and [TESTING_GUIDE.md](TESTING_GUIDE.md) for the teammate's pending manual checks.

## Setup and full regression commands (Windows CMD)

Run from the project root. Keep the master and worker environments separate; running generic discovery in just one environment is not the full supported workflow.

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
master\.venv\Scripts\python.exe -m pip install -r master\requirements.txt
worker\.venv\Scripts\python.exe -m pip install -r worker\requirements.txt
master\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_master*.py" -v
worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -v
master\.venv\Scripts\python.exe -m pip check
worker\.venv\Scripts\python.exe -m pip check
```

No pytest or external HTTP test client is required. The image round-trip test also needs the existing `worker\.venv\Scripts\python.exe` and its dependencies, even when launched from the master environment. Both interpreters must work. Run commands from the root so subprocess imports resolve correctly. Test fixtures are synthesized in memory; master image storage uses temporary directories and is cleaned up.

In a Windows sandbox where asyncio cannot create its internal socketpair, replace only the master discovery command with:

```bat
master\.venv\Scripts\python.exe tests\run_master_tests.py
```

This existing runner discovers the same master suites using a test-only polling event loop. It does not start a server or permit network testing. Do not use it to serve the application. Inspect `Ran N tests` and the final `OK`/`FAILED` output; `echo %ERRORLEVEL%` immediately after a command reports its exit status. Subtests are included within their containing test method, not added to the method counts below.

## Existing suites

| File | Test methods | Scenarios |
| --- | ---: | --- |
| `tests/test_master.py` | 10 | Health, empty registry, registration/listing/logging, duplicate protection, multiple workers, invalid fields/types/lengths, malformed JSON, whitespace normalization, app isolation and Phase 1 OpenAPI routes |
| `tests/test_master_tasks.py` | 14 | Unique task IDs, pending tasks, batch validation/atomicity, round-robin order and cursor, busy-worker exclusion, queued-task dispatch on registration, empty/unknown polling, timestamps/attempts, ownership and transitions, terminal failure, concurrent polls, threaded delivery/completion, registration 409 documentation and snapshots |
| `tests/test_master_images.py` | 5 | Complete image byte round trips for four operations, atomic upload batches, unique safe filenames, corrupt files, MIME/extension checks, oversized dimensions/bytes, operation parameters, owner/state checks, dummy-completion bypass rejection, result dimensions/mode, idempotent upload, immutable completed output, failed/unknown results |
| `tests/test_worker.py` | 5 | Default registration, environment overrides, HTTP rejection/redirect handling, connection/timeout errors, invalid configuration; new polling loop mocked to retain focused Phase 1 tests |
| `tests/test_worker_tasks.py` | 6 | Polling/no-task delay, execution delay and timeouts, start/completion requests, dummy simulated failure, rejected starts, clean interruption, communication failure and invalid timing configuration |
| `tests/test_worker_images.py` | 11 | Pixel comparisons against OpenCV grayscale/resize/blur/edges, JPEG input, invalid images/parameters, mocked HTTP byte download/upload and reporting a processing failure |
| `tests/test_master_monitoring.py` | 15 | Injected clocks, server receipt time, nullable/invalid/nonfinite metrics, session identity, offline reconnect, old task fencing, offline eligibility, background sweep, lifespan cleanup and concurrent heartbeat/task mutations |
| `tests/test_worker_monitoring.py` | 9 | Nonblocking psutil samples, error/invalid sample handling, request payload/token/timeouts, periodic failure waiting, independent thread during blocked processing, rejection handling, main lifecycle/session propagation and configuration validation |
| `tests/test_master_phase5.py` | 21 | Static/adaptive policies, metrics freshness and fallback, low RAM, fairness, history, no migration, concurrent recovery/polling, retries/limits, stale session/generation, legacy downgrade prevention and real image processor byte round trip after reassignment |
| `tests/test_worker_phase5.py` | 4 | Assignment header propagation, network processing failure retry classification, permanent validation failure and no duplicate claim after poll connection failure |
| `tests/test_master_dashboard.py` | 11 | Explicit CORS origins and preflight, denied/invalid origins, public credential-free snapshots, initial/changed/unchanged WebSocket frames, disconnection and network sends outside store lock |
| `tests/test_master_integration.py` | 5 | Encoded Worker ID polling, required routes, private mutation headers, public credential privacy, exact Task state/operation and image multipart/update schemas |
| **Master + Worker total** | **116** | **81 master + 35 worker; benchmark/setup suites are separate below** |

## Frontend tests (introduced Phase 6; expanded Phase 9)

In Windows CMD:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing\frontend
npm ci
npm test
npm run build
npm audit
```

`npm ci` uses the committed package-lock. Run installation only when dependencies are missing/changed; the implementation's actual commands/results are recorded in TEST_RESULTS.md. The frontend uses React, Vite, TypeScript, Tailwind 3/PostCSS and Vitest/RTL with jsdom. No browser is launched by these tests.

| Frontend suite | Methods | Coverage |
| --- | ---: | --- |
| `src/App.test.tsx` | 18 | Real-response-derived counts, loading/error/empty states, task filtering/all statuses, reassignment updates, attempt history/failure display, worker metrics/staleness, read-only scheduling, recorded retries and result URLs/missing images |
| `src/UploadPanel.test.tsx` | 9 | File count/type/byte limits, decoded dimension limits, operation-specific parameters, file submission, tracking returned task IDs, API errors and empty submission |
| `src/api.test.ts` | 4 | Actual endpoint names, credential-free public requests, error handling, multipart fields and encoded result URLs |
| `src/useLiveDashboard.test.tsx` | 7 | Initial fetch/live events, five-second fallback, reconnect/refresh, retained snapshots on error, malformed events, superseded sockets and cleanup |
| **Frontend total** | **38** | Mocked network + component tests |

The test fixture module is imported only by tests; the application never imports or displays fabricated fixture statistics. Backend socket tests use fake WebSocket transport but execute the actual stream/snapshot code; CORS tests use the real middleware through ASGI. A live TCP/browser WebSocket connection, layout screenshots, CORS behavior in a real browser and LAN operation remain separate manual checks. Neither jsdom nor fake sockets establish those passes. All earlier image processor subprocess round trips remain in the Python regression command.

## Phase 7 benchmark tests

Run from repository root using the worker environment:

```bat
worker\.venv\Scripts\python.exe -m unittest discover -s tests -p test_benchmarks.py -v
```

This command is **additional** to all master/worker/frontend tests and the frontend build, not a substitute. `tests/test_benchmarks.py` currently has 24 test methods for deterministic seeded workloads, preservation of existing data, content IDs/correlation, single/static/adaptive configuration, exact topology/isolation, failed/retried/partial/cancelled records, deadline checks, duplicate response IDs, output dimensions, timing/statistics/missing values, matched comparisons, warmup exclusion, JSON/CSV/SVG reporting, real multipart field names/bytes, network failure, hardware metadata validation and CLI rejection of a changed saved manifest before upload. Clocks/API observations are controlled; all generated inputs/results are temporary fixtures.

Tests of formulas intentionally use synthetic numbers to establish arithmetic correctness. They are never copied to benchmarks/results or claimed as experimental performance. Existing master regressions continue real processor subprocess/ASGI image and recovery round trips; benchmark runner HTTP tests mock transport. A real network image benchmark, browser screenshot and LAN experiment remain unperformed unless separately recorded in TEST_RESULTS.md. No benchmarking UI or backend algorithm was added, so earlier frontend suites remain the relevant dashboard regression.

The production build type-checks source and tests before bundling. A later build found four test queries using an unsupported RTL option; those were corrected without excluding tests from type checking. The installed development test dependency tree has unresolved audit findings recorded in TEST_RESULTS.md; the attempted upgrade was blocked by registry DNS access.

## What the round trip proves

`test_complete_http_roundtrips_all_operations` uploads multipart image bytes through the actual FastAPI ASGI application, creates/assigns a task, polls/starts it, downloads its bytes, invokes the real image processor in the worker's separate Python interpreter, uploads the PNG, checks completion/idempotency and compares view/download response bytes. It repeats for grayscale, resize, Gaussian blur and edge detection.

This is an in-process HTTP-contract integration test with a real processor subprocess. It does **not** run Uvicorn over TCP, run the continuous worker HTTP loop across a real network, exercise browser UI, or prove two-laptop operation. Worker network calls are separately checked with mocks. Unit pixel comparisons establish implementation consistency with OpenCV, not independent visual quality evaluation.

## Coverage limits and future maintenance

There is no measured coverage percentage, load benchmark, hostile-input security audit or hardware interoperability certification. Existing tests cover selected size boundaries and failure cases, not every supported parameter combination or every image format variation. Animation rejection and the complete 20-file/16-million-pixel boundaries should also receive manual review; do not infer exhaustive coverage from the inventory.

For every future phase: add meaningful tests, run both relevant earlier-phase regressions and new tests, fix introduced failures, and update all three testing documents. Record failed or blocked runs honestly. A blank manual checklist is never evidence of a pass. Recovery, adaptive scheduling and frontend regressions are implemented and included above; database/ML remain outside scope.

## Phase 4 regression details

Commands remain unchanged and include both new monitoring files. Test clocks advance explicitly; timeout tests do not sleep for ten real seconds. Master lifespan tests enter/exit the actual lifespan context, asserting the sweeper starts and is cancelled. The thread test uses events and bounded waits to verify heartbeat progress while a separate processing action is blocked; it is not a CPU load benchmark or live HTTP run. Existing image ASGI/processor round trips still run for all four operations.

Phase 1 list assertions now compare retained worker_id/hostname fields because GET workers adds monitoring fields; Phase 4 tests validate the complete record. The registration request test now expects the explicit session-v1 protocol header. The image ASGI test helper accepts optional headers for session tests. These adaptations preserve the original regression intent rather than dropping earlier tests.

Session-aware task and image requests are fenced against rotated tokens and previous task-session generations. Legacy requests remain supported only with their earlier trust assumptions; legacy IDs cannot reconnect. No load-adaptive scheduling, retry or task recovery is tested or implemented. Live TCP, hardware load variation and LAN cases remain manual verification work.

## Phase 5 regression details (supersedes Phase 4 no-recovery statements)

The same full-suite commands discover the new Phase 5 files. Static mode stays the default and all earlier tests remain. Three Phase 4 tests were adapted to supply assignment credentials. The earlier no-recovery test retains its method but now asserts a newly counted assignment after reconnect while old-session and missing-generation updates remain rejected; this is an intentional Phase 5 behavior change, not removal of the ownership regression.

Unit tests use injected clocks and controlled resource samples. Recovery concurrency tests repeat simultaneous sweeps and polling without long timeout sleeps. Worker tests check generation header propagation and transient/permanent error reports. An ASGI image recovery test performs multipart input upload, running-worker timeout, assignment to another worker, original-byte download, real processing in the worker interpreter, rejected stale upload, accepted new upload, repeated completion and byte-identical result download. This adds recovery integration coverage without claiming live TCP or LAN execution. Existing tests still exercise all image operations.

Observed results are in TEST_RESULTS.md. No throughput/speedup benchmark, live hardware-load experiment or teammate manual test was performed. Timing history is an input to a policy, not proof of better performance.

## Phase 9 additions and preservation checks

All earlier methods and assertions remain. One exact UI-label assertion now expects Adaptive Scheduling instead of adaptive scheduling; it still requires the actual configured mode. Added methods:

- Six App cases: all six navigation destinations/headings/aria-current; actual Worker load/hostname/heartbeat/MiB labels; absent load without invented zero; retry wording plus current running state; static/adaptive descriptions and no runtime toggle; standalone benchmark formats/definitions/limitations without experimental data.
- Two UploadPanel cases: all operation descriptions/relevant fields; in-flight submission state and unchanged resize payload/defaults. Existing file validation, API failure and no-premature-completion assertions remain.
- Three Worker image cases: boolean/size/threshold boundaries, OpenCV-to-ValueError translation, failed/oversized output encoding. Existing all-operation pixel comparisons protect extracted decode/operation/encode helpers.
- One Master contract case: exact Task state/operation values, multipart files/operation/params fields/default, registration 409 and unchanged update/failure fields. Existing route/header/privacy and behavioral regressions remain.

Run scripts\test_all.cmd for the complete set. Focused commands actually used during development were npm test and npm run build in frontend/, and worker\.venv\Scripts\python.exe -m unittest discover -s tests -p test_worker_images.py -v from the root. TEST_RESULTS.md records the initial new-test fixture assertion failure and corrected full rerun.

No new testing or runtime dependencies. No Master policy/security/route changes; no benchmark formula, transport hook, API client, environment or CMD script changes. Build checks TypeScript and CSS, but jsdom is not visual/mobile/accessibility acceptance. Phase 9 manual cases P9-01–12 remain unexecuted; see TESTING_GUIDE.md.
