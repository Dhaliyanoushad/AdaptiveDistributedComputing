# Automated tests: Phases 1-3

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
| `tests/test_worker_images.py` | 8 | Pixel comparisons against OpenCV grayscale/resize/blur/edges, JPEG input, invalid images/parameters, mocked HTTP byte download/upload and reporting a processing failure |
| **Total** | **48** | **29 master + 19 worker** |

## What the round trip proves

`test_complete_http_roundtrips_all_operations` uploads multipart image bytes through the actual FastAPI ASGI application, creates/assigns a task, polls/starts it, downloads its bytes, invokes the real image processor in the worker's separate Python interpreter, uploads the PNG, checks completion/idempotency and compares view/download response bytes. It repeats for grayscale, resize, Gaussian blur and edge detection.

This is an in-process HTTP-contract integration test with a real processor subprocess. It does **not** run Uvicorn over TCP, run the continuous worker HTTP loop across a real network, exercise browser UI, or prove two-laptop operation. Worker network calls are separately checked with mocks. Unit pixel comparisons establish implementation consistency with OpenCV, not independent visual quality evaluation.

## Coverage limits and future maintenance

There is no measured coverage percentage, load benchmark, hostile-input security audit or hardware interoperability certification. Existing tests cover selected size boundaries and failure cases, not every supported parameter combination or every image format variation. Animation rejection and the complete 20-file/16-million-pixel boundaries should also receive manual review; do not infer exhaustive coverage from the inventory.

For every future phase: add meaningful tests, run both relevant earlier-phase regressions and new tests, fix introduced failures, and update all three testing documents. Record failed or blocked runs honestly. A blank manual checklist is never evidence of a pass. Application state recovery, heartbeat, adaptive scheduling, database and frontend tests belong to later authorized phases.
