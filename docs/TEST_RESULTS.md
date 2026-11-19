# Test results

## Phase 9 baseline and final verification — 2026-11-19

Git was clean before edits. The complete existing suite ran before any Phase 9 modifications, using cmd.exe /d /c scripts\test_all.cmd. All eleven stages completed, exit 0. Baseline local evidence: outputs/verification/94e80d3b-4bde-45c6-83f4-e53f6b289d2d/results.json and per-stage UTF-8 logs. Generated evidence remains ignored, not committed.

After the UI/readability changes and new tests, the same complete command returned 0 with all eleven stages passing. Final local evidence: outputs/verification/46843e24-e75f-4ab3-a551-46348ea7cd95/results.json and per-stage logs; finished_at 2026-11-19T12:07:48.489717+00:00. Each count below is a method/test count; subtests and repeat runs are not added.

| Suite | Baseline passed | Final passed | Final failed | Final errors | Final skipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| Master including HTTP/security/image contracts | 80 | 81 | 0 | 0 | 0 |
| Worker including image processing | 32 | 35 | 0 | 0 | 0 |
| Benchmark | 24 | 24 | 0 | 0 | 0 |
| Frontend component/API/live-update | 30 | 38 | 0 | 0 | 0 |
| Setup/contracts | 7 | 7 | 0 | 0 | 0 |
| **Total** | **173** | **185** | **0** | **0** | **0** |

Baseline also had zero failures/errors/skips. Final durations: Master 5.921 seconds, Worker .326 seconds, benchmark .555 seconds, setup .017 seconds; frontend four files/38 tests, 6.24 seconds. Actual additional stages passed before and after: TypeScript/Vite production build (baseline bundling 2.65 seconds; final 2.55 seconds), both python -m pip check (No broken requirements found), and Master/Worker/frontend launch.py --check (configuration checked; services not started). No dependency installation or audit remediation was performed in Phase 9.

Focused development runs (history, not extra unique passes):

- Worker image suite: 11 passed, 0 failures/errors/skips in .270 seconds using the Worker interpreter.
- Initial frontend npm test: 38 total, 37 passed and 1 failed, 0 skipped. A newly added retry-text test incorrectly expected completed-state text from the existing running Task fixture. Corrected it to assert the running-state explanation while retaining the recorded-retry assertion. No production workaround or deleted/loosened earlier assertion was used.
- The production build run immediately after that focused frontend failure passed (2.71 seconds bundling); it did not turn the failed test run into a pass. The final complete rerun above passed all 38 frontend tests and the build.

Verified automatically: original registration/metrics/heartbeat/reconnect, task queue/polling/ownership, scheduling/fairness/fallback, retry/session/assignment/stale-output protection, all-operation ASGI byte round trips with real Worker OpenCV subprocess, benchmark arithmetic/exports, UI navigation/labels/validation/state/history/result links, WebSocket reconnect/poll fallback and setup contracts. New boundary tests protect the extracted image helpers. Master behavior, scheduling/recovery/security, benchmark formulas, frontend transport/client and startup/config scripts have no implementation changes in this phase.

Limits and unresolved issues remain: Master tests use the socket-free test runner/ASGI rather than live Uvicorn TCP; frontend uses jsdom/mocked transport rather than a real browser. No browser screenshots, responsive/accessibility acceptance, clean-machine installation, two-laptop LAN checks, sustained hardware tests or real benchmark trials were performed. Phase 9 does not resolve prior WinError 10013 or npm audit findings (1 moderate/2 critical development findings; the earlier production-only zero does not clear them). In-memory restart loss and trusted-LAN enrollment/security limitations remain. No claim of adaptive speedup or exhaustive correctness is made.

Teammate manual cases, including all preserved Phase 1–8 procedures and P9-01–12, are **NOT YET EXECUTED**; outcome fields remain blank. Docs changes are not test execution. Read later records below as historical phase evidence rather than current limitations superseded by authorized later phases.

## Phase 8 final verification — 2026-11-19

Actual one-command execution: `cmd.exe /d /c scripts\test_all.cmd` returned **0** after all eleven stages completed. Retained local evidence: `outputs/verification/817a5e54-1b48-4c69-a60f-c4d63c270d78/results.json` and per-stage UTF-8 logs (ignored, not committed).

| Suite | Passed | Failed | Errors | Skipped | Actual result |
| --- | ---: | ---: | ---: | ---: | --- |
| Master regression + final HTTP contracts | 80 | 0 | 0 | 0 | OK; 5.516 seconds |
| Worker regression | 32 | 0 | 0 | 0 | OK; 0.311 seconds |
| Benchmark tests | 24 | 0 | 0 | 0 | OK; 0.542 seconds |
| Setup/config/script tests | 7 | 0 | 0 | 0 | OK; 0.022 seconds |
| Frontend component/API/live-update tests | 30 | 0 | 0 | 0 | Four files passed; 6.12 seconds |
| **Unique methods in final run** | **173** | **0** | **0** | **0** | Earlier phase functionality retained |

Other stages actually passed: frontend TypeScript/Vite production build (2.61 seconds bundling), master and worker pip check (no broken requirements), master/worker/frontend launcher --check (non-serving). Direct CMD startup --check wrappers and workload/report/runner --help wrappers also passed. scripts/setup.cmd was reviewed but **not executed as a clean installation**, because environments/dependencies already exist and package-index access is restricted. Real service startup/shutdown through the new wrappers is not claimed by configuration checks.

Introduced/fixed issues and retained run history:

- First final-contract master run: 80 methods, 79 passed and 1 failure. A worker_id containing '/' registered but could not poll (404). Worker detail/polling routes now use path-aware parameters; the regression passes. Session/ownership checks were preserved; scheduling/recovery algorithms did not change.
- First unified run passed Python stages, then the new verification wrapper raised UnicodeEncodeError while printing Vitest checkmarks under Windows CP1252. Its partial UTF-8 logs remain in outputs/verification; it was not a full verification pass. Added console escaping and incremental JSON evidence saving, plus a regression test.
- Final unified rerun above passed all stages. No interrupted-run logs were deleted or represented as completed evidence.

## Phase 8 safe network investigation — observed, not remediated

Executed `master\.venv\Scripts\python.exe scripts\diagnose_network.py` and a read-only Get-NetTCPConnection filter for ports 8000/5173:

| Probe | Actual observation |
| --- | --- |
| Ephemeral 127.0.0.1 bind/listen | Passed |
| 127.0.0.1:8000 bind/listen | Passed; socket closed afterward |
| 127.0.0.1:5173 bind/listen | Passed; socket closed afterward |
| Connect to owned ephemeral loopback listener | Failed: WinError 10013 / errno 13 |
| socket.socketpair child | Blocked beyond 4 seconds; only owned diagnostic child terminated |
| registry.npmjs.org getaddrinfo child | Failed: socket.gaierror 11001 |
| Application-port listener query after probes | No matching listener rows returned in this context |

This supports an execution-context/security restriction on socket connections, not an application port conflict at that observation. It does **not** identify a specific firewall/antivirus policy or prove unrestricted behavior under the user's normal terminal. No firewall, antivirus, registry, network profile or system-wide policy was changed. Exact commands and safe target-machine remediation options are in TWO_LAPTOP_SETUP.md. Previous browser/TCP/LAN blocks are not marked resolved.

## Phase 8 security audit and handoff status

Rechecked full `npm audit --json`: still **1 moderate and 2 critical development-tool findings** (exit 1). `npm audit --omit=dev`: **0 production findings** (exit 0). Retried compatible `npm install --save-dev vitest@4.1.12 --fetch-retries=0 --fetch-timeout=20000`: failed ENOTFOUND; no forced upgrade or package-tree change. Full security audit remains unresolved despite passing tests/build.

Tracked-file review found source/docs/placeholders, not virtual environments, node_modules, uploaded/generated datasets, actual .env secrets or output evidence. `git check-ignore` confirmed the intended exclusions for all components, benchmark data and verification outputs. A targeted secret-pattern source scan found no matching private-key/password/token assignments; this is a limited review, not a formal secret/security audit. Private credential exclusion is separately tested in public snapshots/HTTP contracts. Meaningful evidence was preserved; no unrelated files were removed.

Manual acceptance: **not yet executed by teammate**. No fresh-machine installation, successful live browser/TCP startup, two-laptop LAN test or real performance experiment was completed during Phase 8. Existing ASGI/processor integration and mocked frontend tests are automated evidence only. The code/docs/scripts are ready to hand off for target-machine manual testing, subject to socket/package-access limitations and development advisories. No manual validation certificate, production-readiness claim or additional phase is implied.

## Phase 7 verification — 2026-11-19

| Actual command | Passed | Failed | Errors | Skipped | Observed result |
| --- | ---: | ---: | ---: | ---: | --- |
| Master environment: `python tests/run_master_tests.py` | 76 | 0 | 0 | 0 | Exit 0; 7.660 seconds |
| Worker environment: `python -m unittest discover -s tests -p "test_worker*.py" -q` | 32 | 0 | 0 | 0 | Exit 0; 0.374 seconds |
| Frontend: `npm test` | 30 | 0 | 0 | 0 | Four files passed; 6.79 seconds |
| Worker environment: `python -m unittest discover -s tests -p test_benchmarks.py -q` | 24 | 0 | 0 | 0 | Final targeted rerun exit 0; 0.630 seconds |
| **Latest unique test methods** | **162** | **0** | **0** | **0** | All earlier regressions + benchmark fixtures |

The full earlier-phase regression and initial 23 benchmark methods passed before the final CLI manifest check was added; its final 24-method targeted rerun also passed. Earlier development benchmark runs passed 19 methods, then 23; these are not additional unique coverage. All benchmark observations generated by these tests are temporary **mock fixtures**, not performance measurements. No fixture charts/results were published under benchmarks/results.

Other actual checks:

- Frontend `npm run build`: TypeScript/Vite production build passed, 2.54 seconds bundling; ignored dist artifacts generated.
- Master and worker `pip check`: both passed (`No broken requirements found.`). No benchmark dependencies added; scripts use existing worker requests/Pillow/psutil and the standard library.
- Benchmark runner `--help`: passed. This is CLI validation only, not a benchmark trial.
- `git diff --check`: passed with normal Windows line-ending warnings.
- Rechecked `npm audit --json`: still **1 moderate and 2 critical development dependency findings**, exit 1. No remediation is claimed.
- Retried `npm install --save-dev vitest@4.1.12 --fetch-retries=0 --fetch-timeout=20000`: failed with **ENOTFOUND registry.npmjs.org**. No forced upgrade or dependency-tree change was made.

## Phase 7 experimental results — none executed

No actual single-device, static-distributed, adaptive-distributed, fault-injection performance trial, live browser test or two-laptop LAN benchmark was performed. There are no measured performance results, speedup/efficiency claims, or teammate manual passes to report. The previous **WinError 10013** live localhost/browser restriction remains an open verification limit; it was not reclassified as resolved. Existing ASGI tests still exercise real image processing and recovery using processor subprocesses, but those tests are not timed deployment benchmarks.

The new CLI/reporting logic is tested with controlled clocks and mocked transport. A multipart HTTP adapter test verifies actual existing field names and image bytes; all existing image/recovery pipeline regressions ran. Live runner interaction with an isolated master/real worker pool remains pending. Manual Phase 7 cases and Pass/Fail fields are appended to TESTING_GUIDE.md and intentionally blank. Hardware/network metadata must be supplied from observations before a real run; template placeholders are rejected.

No master/worker/frontend runtime behavior or scheduling/fault-recovery algorithm was changed in Phase 7. Reports are standalone, generated from recorded run files only; no benchmarking UI was added. Master restart persistence, pure worker-only processing instrumentation, hardware attestation and hard real-time HTTP cancellation remain unsupported. Stop after Phase 7; no Phase 8 features were implemented.

## Phase 6 final regression — 2026-11-19

| Command | Passed | Failed | Errors | Skipped | Actual result |
| --- | ---: | ---: | ---: | ---: | --- |
| Master `python tests/run_master_tests.py` in its existing environment | 76 | 0 | 0 | 0 | Exit 0; 6.411 seconds; includes all prior regressions and 11 dashboard cases |
| Worker `python -m unittest discover -s tests -p "test_worker*.py" -q` in its existing environment | 32 | 0 | 0 | 0 | Exit 0; 0.259 seconds |
| Frontend `npm test` | 30 | 0 | 0 | 0 | Four Vitest files passed; 5.79 seconds; mocked HTTP/WebSocket + jsdom |
| **Latest unique tests** | **138** | **0** | **0** | **0** | 108 Python + 30 frontend |

The commands above ran from repository root for Python and frontend/ for npm. Existing Python image subprocess round trips (including recovery) ran as part of master regressions. CORS middleware was exercised through ASGI; stream tests used fake WebSocket transport and actual public snapshot/stream code. They checked origin policy, changed/unchanged state, disconnection, credential exclusion and lock release before sending.

Additional executed checks:

- `npm run build`: TypeScript check and Vite production bundling passed; generated frontend/dist is ignored. Final artifacts: CSS approximately 22.56 kB, JS approximately 244.01 kB (filenames may change with content). This is build output size, not a runtime performance claim.
- Master and worker `pip check`: both passed, no broken requirements.
- `npm audit --json`: **failed audit**, 1 moderate + 2 critical findings in the development Vitest/@vitest/mocker/tinypool tree. These findings are unresolved.
- `npm audit --omit=dev`: exit 0, **0 production-dependency vulnerabilities reported**. This does not clear the full development-tree audit.
- `npm install --save-dev vitest@4.1.12 --fetch-retries=0 --fetch-timeout=20000`: failed with registry DNS `ENOTFOUND`; no patched version was installed. A registry metadata lookup also failed. Keep this as an explicit development-tool maintenance blocker, not a successful remediation.

Development history (not additional unique passes): initial npm install succeeded with 226 packages and the audit findings above. Initial frontend tests passed 27 cases; later suites expanded to 30. An intermediate production build failed on four unsupported `exact` options in RTL role queries; the test source was corrected, and later full type-check/build passed without excluding tests. Initial Python dashboard run passed 75 master and 32 worker methods; the final master suite added a lock-release test for 76.

Live verification limits: Vite dev server launched and printed localhost:5173 ready. A direct Python HTTP readiness request then failed with **WinError 10013 (socket access forbidden)**. Uvicorn launch produced no ready output and was stopped. Both owned server sessions were stopped. No successful live dashboard HTTP integration, real browser, screenshots, visual acceptance or two-laptop LAN run is claimed. Browser console, responsive layout, actual WebSocket reconnect behavior and LAN/firewall checks remain pending teammate cases. Detailed manual Pass/Fail cells remain blank.

No scheduling/recovery algorithm was changed in Phase 6. No database, benchmarking or Phase 7 functionality was introduced. Remaining issues include the unresolved development-tool advisories and blocked live/browser verification; existing in-memory persistence/authentication limitations remain.

## Phase 5 final regression — 2026-11-19

| Command | Passed | Failed | Errors | Skipped | Actual result |
| --- | ---: | ---: | ---: | ---: | --- |
| `master\.venv\Scripts\python.exe tests\run_master_tests.py` | 65 | 0 | 0 | 0 | Exit 0; 5.542 seconds; OK |
| `worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -q` | 32 | 0 | 0 | 0 | Exit 0; 0.256 seconds; OK |
| **Latest full suite** | **97** | **0** | **0** | **0** | All earlier-phase tests plus Phase 5 |

Both existing environments' `pip check` passed with `No broken requirements found.` No new package dependencies were added. `git diff --check` passed, with normal Windows line-ending warnings.

Earlier Phase 5 development runs, retained as history rather than added pass counts:

- First compatibility run: master 44 methods, 41 passed and 3 errors (0 assertion failures). The session-aware Phase 4 fixtures omitted the newly required assignment token. Worker 28 passed.
- Updated session fixtures and expanded scheduler/recovery run: master 64 passed, worker 28 passed. The earlier no-recovery expectation was updated for a new counted assignment while preserving stale-owner rejection.
- Final expanded run: 65 master and 32 worker passed as recorded above. No failed or skipped methods remain in that run.

Verified: static baseline, controlled low/high CPU/RAM selection, missing/stale metrics and cold start, RAM threshold, session eligibility, busy/offline exclusion, fairness, processing history, no running migration, assigned/running timeout recovery, concurrent recovery/claim deduplication, pending preservation, retry budget/permanent failure, session and assignment fencing, legacy retry downgrade protection and idempotent completion. The new image ASGI test transferred original bytes after reassignment, invoked real OpenCV processing in the worker interpreter and confirmed stale results could not alter the one accepted output. Earlier all-operation image tests also ran.

Limits: master tests use the existing socket-free ASGI runner. No live TCP, manual, two-laptop LAN, sustained hardware-load or performance benchmark run was performed for Phase 5. Manual checklist cells remain blank. No adaptive speedup is claimed. Persistence after master restart remains unsupported. Legacy clients have no secure retry capability; an offline legacy attempt fails terminally. Adaptive cold/stale-metric fallback is a policy choice, not evidence of available RAM. Heartbeating but permanently hung work has no independent task execution deadline in this phase.

## Phase 4 final regression — 2026-11-19

Latest observed full-suite results (earlier records below remain historical):

| Command | Passed | Failed | Errors | Skipped | Observed result |
| --- | ---: | ---: | ---: | ---: | --- |
| `master\.venv\Scripts\python.exe tests\run_master_tests.py` | 44 | 0 | 0 | 0 | Exit 0; 5.673 seconds; OK |
| `worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -q` | 28 | 0 | 0 | 0 | Exit 0; 0.322 seconds; OK |
| **Latest full suite** | **72** | **0** | **0** | **0** | Includes all Phase 1-3 regressions and 24 Phase 4 methods |

Both environments' `pip check` commands returned `No broken requirements found.` No dependencies were added for Phase 4. `git diff --check` returned no whitespace errors, with normal Windows line-ending warnings.

Phase 4 development-run history, not additional unique test coverage:

- Adapted earlier-phase regression run: 29 master passed and 19 worker passed.
- First monitoring suites: 42 master passed and 26 worker passed.
- Expanded suites: 44 master passed; worker ran 28 with 27 passing and 1 error. The new lifecycle/session-header test reused a registration mock with HTTP 201 for a task update expecting 200. The mock was corrected; no production workaround was introduced.
- Worker rerun after fixture correction: 28 passed, 0 failures/errors (0.229 seconds).
- Final full rerun is recorded in the table above. Expected negative-test warning messages about unavailable metrics, invalid settings and heartbeat failure are not suite failures.

Verified scenarios include injected monotonic/UTC clocks, timeout boundary, independent periodic sweep without GET, actual lifespan startup/cancellation, online duplicate rejection, offline session rotation, stale token/task-session fencing, nullable/invalid metrics, concurrency, nonblocking psutil calls, bounded heartbeat waits and thread shutdown. A synchronized thread test checks heartbeat progress while a processing action is blocked; it is not a long-duration real-image stress test. Existing ASGI image byte round trips still invoke the real worker image processor for all four operations.

No live TCP, teammate visual/manual acceptance or two-laptop LAN test was performed for Phase 4. The existing in-process runner avoids the previously observed Windows socketpair restriction; standard network-based master discovery/serving was not rerun here. Manual checklist cells remain blank.

Remaining product limits: legacy registrations retain trusted-network identity semantics and cannot reconnect; session tokens fence modern reconnects but do not authenticate initial enrollment. Old assigned/running tasks remain stuck and keep the worker ID busy after reconnect; no retry, requeue or recovery exists. Metadata is in memory. Heartbeat shutdown is bounded/best effort around HTTP timeouts; DNS/OS stalls may outlast Requests timeouts. Live hardware metrics/latency and LAN behavior remain for the teammate. No Phase 5 functionality was implemented.

## Actual automated rerun — 2026-11-19

Executed from the existing Windows repository using separate master and worker virtual environments. Both interpreters reported **Python 3.13.2**. These results describe this run only; no changes to application behavior or tests were made for this documentation task.

| Command | Passed | Failed | Errors | Skipped | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `master\.venv\Scripts\python.exe tests\run_master_tests.py` | 29 | 0 | 0 | 0 | Exit 0; `Ran 29 tests in 2.567s`, `OK` |
| `worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -v` | 19 | 0 | 0 | 0 | Exit 0; `Ran 19 tests in 0.256s`, `OK` |
| **Total test methods** | **48** | **0** | **0** | **0** | Includes existing Phases 1-3 tests |

Additional checks actually executed:

- Each environment's `python --version`: Python 3.13.2.
- Each environment's `python -m pip check`: `No broken requirements found.` These are dependency consistency checks, not additional test methods.

## Scope and limitations

- The existing test-only master runner was used because earlier attempts in this session history found a Windows asyncio socketpair restriction. Standard master discovery was not rerun during this documentation task; no new result is claimed for that command.
- The master image round-trip method exercised all four operations through ASGI endpoints and a real processor subprocess in the worker environment. Multipart transfer, task state, output upload and completed image downloads were checked.
- No live Uvicorn/TCP integration, browser visual assessment, multi-device performance measurement or two-laptop LAN test was run during this rerun. Mocked worker requests do not establish real network connectivity.
- Earlier implementation runs are recorded in `phase1.md`, `phase2.md` and `phase3.md`; they are historical evidence, not additional passes counted here. Earlier failed installs/blocked runs remain documented in the environment reports.
- Unresolved verification gaps: live TCP image processing, visual quality across real photos, firewall/router behavior and different hardware. There were no automated test failures in this rerun.
- Existing product limits remain: in-memory metadata resets on restart, no worker reconnection/retries/redelivery, no heartbeat/recovery, no authentication, endpoint-level file limits after multipart parsing, and structural output validation rather than proof of correct work by an untrusted worker.

## Teammate manual testing — not performed yet

No teammate manual results have been supplied. All Pass/Fail cells in [TESTING_GUIDE.md](TESTING_GUIDE.md) are intentionally blank. Two-laptop LAN testing is **pending**, not passed. Development and automated verification do not replace teammate acceptance testing.

When manual testing occurs, append the actual date, tester, commit/revision, OS/Python versions, device details, case IDs, observed status/body, Pass/Fail outcome and evidence. Preserve failures and retest history. Do not prefill expected outcomes as observed results.
