# Consolidated teammate testing guide — Phases 1–8

## Current handoff entry point and evidence status

Use README.md and Phase 8 below for current relative commands. Earlier phase procedures retain their original objectives/prerequisites/actions/inputs/expected responses; later scope updates supersede historical no-recovery/no-frontend statements. Use TEST_EXECUTION_TEMPLATE.md for each case, never expected results as assumed passes.

| Category | Current status |
| --- | --- |
| Automated execution | TEST_RESULTS.md and ignored outputs/verification/UUID logs; not manual acceptance |
| Teammate manual checks verified with evidence | None supplied; no case pre-marked Pass |
| Localhost/browser/LAN/performance acceptance | NOT YET EXECUTED unless a later record proves otherwise |
| Restricted-context socket operation | BLOCKED: ephemeral connect WinError 10013 despite successful binds |
| Development-tool remediation | BLOCKED by registry DNS; 1 moderate/2 critical findings remain |

Outcome choices throughout are **Pass / Fail / Blocked / Not Tested**. Leave cells blank until executed. TEST_EXECUTION_TEMPLATE.md supplies objective, prerequisites, actions, inputs, expected/actual, evidence, defects and retest fields for every phase case.

**Phase 5 compatibility update:** Sections 1-8 remain as historical phase procedures. The Phase 5 section supersedes earlier expectations of stuck modern-worker tasks after timeout. They are now retried up to the configured budget. Session-aware hand-driven task/image requests additionally need `X-Task-Assignment` from the polling response. Legacy manual Phase 1-3 examples remain first-attempt/static compatibility tests only. Never interpret historical no-recovery statements as the current Phase 5 policy.

**Phase 4 compatibility note:** the earlier sections are preserved as historical procedures. Current `/workers` records add status/metrics. Reconnection is now available only for session-aware workers after offline detection; the Phase 4 section below supersedes older statements that all reconnection is unsupported. For the slow hand-driven Phase 1-3 registration/poll/update exercises, start the master with `set "WORKER_TIMEOUT=3600"` so legacy manual identities do not expire in 10 seconds. Use a fresh master and reset this to 10 for Phase 4 timeout cases. Do not leave a long timeout enabled when measuring offline detection.

**Manual testing has not been performed by the teammate yet.** Everything below is a procedure and expected outcome, not an observed pass. Record results in the blank checklist at the end and append actual evidence to [TEST_RESULTS.md](TEST_RESULTS.md). Automated suites and their limits are described in [AUTOMATED_TESTS.md](AUTOMATED_TESTS.md).

## 1. Prepare Windows CMD

Open **Command Prompt** (Start menu → type `cmd`). These commands use CMD syntax, not PowerShell. Replace the project directory if your copy is elsewhere.

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
python --version
node --version
npm --version
git --version
```

Python should be 3.13.2 for the recorded baseline. Node/npm are reserved for future frontend development and are not needed to run current tests. Keep both Python environments separate. If the environments already exist, preserve them; only run a creation command when its corresponding environment is missing:

```bat
if not exist master\.venv\Scripts\python.exe python -m venv master\.venv
if not exist worker\.venv\Scripts\python.exe python -m venv worker\.venv
master\.venv\Scripts\python.exe -m pip install -r master\requirements.txt
worker\.venv\Scripts\python.exe -m pip install -r worker\requirements.txt
master\.venv\Scripts\python.exe -m pip check
worker\.venv\Scripts\python.exe -m pip check
```

Expected: installation succeeds and both checks say `No broken requirements found.` Stop and record setup failures rather than treating later tests as passed. Activation is optional because commands select the interpreter directly. Optional activation in separate terminals is `master\.venv\Scripts\activate.bat` or `worker\.venv\Scripts\activate.bat`.

Use four CMD windows: **A master**, **B worker 1**, **C worker 2**, **D API requests**. Run `cd /d ...` in every window. Ctrl+C stops a running server/worker. A **fresh master** means stop all workers, stop the master, then start the master again. This clears metadata and prevents stale worker IDs. Files in `uploads/` and `outputs/` remain; do not delete unrelated files.

Window A:

```bat
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

Expected: startup completes on port 8000. Run one master process, without `--reload` or multiple workers. A browser at `http://127.0.0.1:8000/docs` shows Swagger. Expand an endpoint → **Try it out** → enter fields/JSON → **Execute**. Inspect both HTTP status and response body. `curl.exe -i` prints headers/status in CMD; curl's exit code alone does not prove an HTTP success.

## 2. Phase 1: registration and health

Start with a fresh master and no worker processes. In D:

```bat
curl.exe -i http://127.0.0.1:8000/health
curl.exe -i http://127.0.0.1:8000/workers
curl.exe -i -X POST http://127.0.0.1:8000/workers/register -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\",\"hostname\":\"test-host\"}"
curl.exe -i http://127.0.0.1:8000/workers
```

Expected, in order: 200 with `{"status":"ok"}`; 200 with `[]`; 201 with the submitted worker record; 200 with an array containing it. Master logs contain a registration event. Repeat the same POST: 409 with `{"detail":"Worker ID already registered"}`; the original hostname must not change. `/docs` must document the 409 response.

Use Swagger to submit `{}`, `{"worker_id":"" ,"hostname":"host"}`, a numeric worker ID, a missing hostname or an extra field: each should return 422 and leave the registry unchanged. IDs/hostnames are trimmed; whitespace-only values fail. Limits: worker ID 128 characters, hostname 253. IDs are case-sensitive. A malformed JSON body also returns 422.

To test real worker registration, use a fresh master, then in B:

```bat
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=worker-1"
set "POLL_INTERVAL=1"
set "TASK_DELAY=3"
worker\.venv\Scripts\python.exe worker\worker.py
```

Expected: successful registration with the actual detected hostname; the worker stays polling. Launch another process with the same ID: registration must fail with HTTP 409 and exit 1 (`echo %ERRORLEVEL%` after exit). Reconnection is unsupported. Without environment overrides, the master URL defaults to loopback and worker ID defaults to hostname; `.env` files are not automatically loaded.

## 3. Phase 2: queue, distribution and lifecycle

### Pending tasks and explicit transitions

Use a fresh master with no worker processes. In Swagger **POST /tasks**, submit:

```json
{"tasks":[{"operation":"dummy","payload":{"label":"first"}},{"operation":"dummy","payload":{"label":"second"}}]}
```

Expected 201 with two unique task IDs, status `pending`, assigned_worker null, attempt_count 0 and UTC created/updated timestamps. GET `/tasks` lists both; GET `/tasks/{task_id}` returns one; an unknown ID returns 404. Copy the first ID:

```bat
set "TASK_ID=PASTE_FIRST_TASK_ID"
curl.exe -i http://127.0.0.1:8000/tasks/%TASK_ID%
```

Register `manual-a` and `manual-b` through Swagger (do not launch those worker processes). Expected: first task assigned to manual-a, second to manual-b, attempt_count 1 and assigned_at set. Registered idle workers are eligible; only one active task per worker.

In D, for the first task:

```bat
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%TASK_ID%/start -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\"}"
curl.exe -i -X POST http://127.0.0.1:8000/workers/manual-a/next-task
curl.exe -i -X POST http://127.0.0.1:8000/workers/manual-a/next-task
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%TASK_ID%/complete -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\"}"
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%TASK_ID%/start -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\"}"
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%TASK_ID%/complete -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-b\"}"
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%TASK_ID%/complete -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\"}"
```

Expected in order: 409 (must poll before start); 200 with the first task; 200 with `{"task":null}`; 409 (must start before completion); 200/running with started_at; 409 (wrong owner); 200/completed with completed_at. Repeat the last command: 200 with unchanged timestamps and attempts. Starting the completed task returns 409. An unknown worker's polling endpoint returns 404. Another worker never receives this task ID; manual-b has its own second task.

For the second task, poll manual-b, start using its ID, then POST `/tasks/{second_id}/fail` with `{"worker_id":"manual-b","error":"manual simulated failure"}`. Expected 200/failed, failed_at set, completed_at null and stored error. Completing or failing it again returns 409. Missing/blank failure error returns 422. States are `pending → assigned → running → completed/failed`.

Empty task batches, unsupported operations and extra task fields return 422 without partial task creation. Dummy batches permit 1-1000 tasks.

### Two real local worker processes

Fresh master. Start B using worker-1 commands above. Start C with the same commands but `WORKER_ID=worker-2`. Wait for both to appear in `/workers`. In D:

```bat
curl.exe -i -X POST http://127.0.0.1:8000/tasks -H "Content-Type: application/json" -d "{\"tasks\":[{\"operation\":\"dummy\"},{\"operation\":\"dummy\"},{\"operation\":\"dummy\"},{\"operation\":\"dummy\",\"payload\":{\"fail\":true}}]}"
curl.exe http://127.0.0.1:8000/tasks
```

Expected on a fresh idle registry: initial two assignments follow registration order; remaining tasks stay pending. Inspect repeatedly: three complete, one fails by simulation, attempt_count stays 1, both workers log work. Busy workers are skipped; later assignments/completion order can vary with timing and faster workers may do more work. This is static scheduling, not load-adaptive scheduling.

Stop a worker during a dummy task: it remains assigned/running; no retry/recovery is expected. Restarting that ID fails with 409. Restart the whole master and workers to reset the demonstration. A stopped worker's registry entry is not proof of liveness.

## 4. Phase 3: image processing

Fresh master and two workers with unique IDs. Put a small JPG and PNG with visible detail in `test_images/` as `one.jpg` and `two.png` (or replace the names below). No worker-side copy is required. Window D:

```bat
curl.exe -i -X POST http://127.0.0.1:8000/images/tasks -F "files=@test_images\one.jpg;type=image/jpeg" -F "files=@test_images\two.png;type=image/png" -F "operation=grayscale"
curl.exe http://127.0.0.1:8000/tasks
curl.exe -i -X POST http://127.0.0.1:8000/images/tasks -F "files=@test_images\two.png;type=image/png" -F "operation=resize" -F "params={\"width\":320,\"height\":240}"
curl.exe -i -X POST http://127.0.0.1:8000/images/tasks -F "files=@test_images\two.png;type=image/png" -F "operation=gaussian_blur" -F "params={\"kernel_size\":5}"
curl.exe -i -X POST http://127.0.0.1:8000/images/tasks -F "files=@test_images\two.png;type=image/png" -F "operation=edge_detection" -F "params={\"threshold1\":100,\"threshold2\":200}"
```

Each request should return 201, one task per file. Wait for completion; image tasks can finish too fast to observe every intermediate state. Workers download actual bytes, process and upload PNG bytes. Task payloads contain parameters/source dimensions, not master-local paths. In Swagger **POST /images/tasks**, select multiple files, operation and the `params` JSON string to repeat interactively.

| Operation | Expected output |
| --- | --- |
| grayscale | 8-bit grayscale, original dimensions |
| resize | Exactly 320×240 in this example; aspect ratio is not automatically retained |
| gaussian_blur | Original dimensions; softened detail; odd kernel 1-99, default 5 |
| edge_detection | Original dimensions; grayscale edge map; thresholds 0-255 in ascending order |

Resize dimensions must each be 1-4096 and total pixels <=16 million. All outputs are PNG. Source EXIF orientation is not applied, and alpha is discarded by OpenCV's color decode.

Copy a completed image task ID and inspect/download (choose a new local filename to preserve earlier downloads):

```bat
set "IMAGE_ID=PASTE_COMPLETED_IMAGE_TASK_ID"
curl.exe -i http://127.0.0.1:8000/tasks/%IMAGE_ID%
curl.exe -f http://127.0.0.1:8000/tasks/%IMAGE_ID%/result/download -o outputs\teammate-result-01.png
```

Expected 200 and a readable PNG. Open `http://127.0.0.1:8000/tasks/YOUR_IMAGE_ID/result` in a browser to view inline. Download endpoint sends an attachment. Confirm dimensions in image properties and compare visually with the original. Unknown/unfinished results return 404. `uploads/` and `outputs/` contain UUID filenames; same-named source images must not overwrite each other.

### Manual ownership/result rejection checks

Use another fresh master with no worker processes. Register manual-a and manual-b, upload one grayscale image, note its ID/owner (manual-a on this fresh registry). Poll manual-a and start the task as in Phase 2. Download input and then post an image output:

```bat
set "IMAGE_ID=PASTE_IMAGE_TASK_ID"
curl.exe -i "http://127.0.0.1:8000/tasks/%IMAGE_ID%/input?worker_id=manual-b"
curl.exe -f "http://127.0.0.1:8000/tasks/%IMAGE_ID%/input?worker_id=manual-a" -o test_images\downloaded-input-01.png
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%IMAGE_ID%/complete -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\"}"
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%IMAGE_ID%/result -F "worker_id=manual-b" -F "file=@outputs\teammate-result-01.png;type=image/png"
```

Expected: wrong-worker download 409; owner download 200; completion bypass 409. Use a previously downloaded **valid grayscale PNG of exactly the source dimensions** for the last request to isolate ownership: expect 409. If dimensions/mode are wrong, structural validation may return 422 before ownership is checked. Then upload the same file as manual-a: expect 200/completed. Repeat identical bytes: 200 with unchanged task metadata. Different valid bytes of the same dimensions cannot replace the result (409). Never use a color image as the valid grayscale fixture.

Before the valid result, try a corrupt PNG, a wrong-sized PNG and a color PNG: 422, task remains running. Before start, an otherwise structurally valid result returns 409. For resize use a result with requested target dimensions. Fail an image task explicitly through `/fail` and verify result upload returns 409 and result GET returns 404. Master validates output structure/ownership, not proof of computation by an untrusted worker.

### Upload and parameter negative cases

Repeat `/images/tasks` with the following fixtures/parameters, using Swagger where easier. Compare GET `/tasks` before/after rejected batches: no tasks from the rejected batch should appear.

| Input | Expected |
| --- | --- |
| Text file MIME `text/plain` or `.txt` filename | 415 |
| Corrupt bytes named `.png` with `image/png` | 422 |
| Encoded image >10 MiB | 413 |
| Valid image width/height >4096 or >16 million pixels | 422 |
| Animated image | 422 |
| No files or >20 files | 422 |
| Mixed valid/corrupt batch | 422; no partial tasks; staged files removed |
| Resize width 0/missing height, even blur kernel, reversed thresholds, unknown parameter/operation | 422 |

Use duplicate source filenames: server-generated stored names must be distinct. For path traversal testing, Swagger/CMD can submit a filename such as `../../escape.png`; it must not create files outside `uploads/`. The automated suite supplies this filename explicitly. Do not modify or delete files outside the test workspace to perform this check.

## 5. Future two-laptop LAN test — pending

Use a trusted private Wi-Fi network. No LAN test is claimed as completed. On the master laptop, run `ipconfig` and record the active Wi-Fi IPv4 address, for example `192.168.1.10`. Stop the local master/workers, then start A with:

```bat
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 0.0.0.0 --port 8000
```

If Windows Firewall asks, permit the Python server only on the trusted Private network. Do not disable the firewall globally or expose this unauthenticated prototype to the internet. On laptop 2, copy/clone source (not virtual environments), open CMD in its project folder and run:

```bat
python -m venv worker\.venv
worker\.venv\Scripts\python.exe -m pip install -r worker\requirements.txt
set "MASTER_URL=http://192.168.1.10:8000"
set "WORKER_ID=lan-worker-2"
worker\.venv\Scripts\python.exe worker\worker.py
```

Substitute the actual IPv4 address. `127.0.0.1` refers to the current laptop; `0.0.0.0` is a bind address, not a worker destination. Confirm health and registration from laptop 2 using the master's IP. Submit dummy and image batches from the master using the earlier commands. Confirm laptop 2 logs execution and its assigned tasks complete with downloadable results. **Do not copy uploaded input images to laptop 2**; this demonstrates byte transfer rather than shared paths. Record both devices' specs, addresses, task IDs, statuses and downloaded-result evidence. Stop services afterward and return future local master runs to loopback binding.

## 6. Troubleshooting and known limits

| Symptom | Check/action |
| --- | --- |
| Python/module not found | Run from project root; use the correct environment executable and install its requirements |
| Pip cannot find/download packages | Check package index/network access; record setup as blocked rather than claiming compatibility |
| Port 8000 in use | Stop the previous project server with Ctrl+C; do not kill unrelated processes |
| Worker connection refused | Start master first; check URL/port and `/health` |
| WinError 10013 or asyncio startup stall | Restricted socket access may block serving/testing; use the documented in-process runner for automated contracts, and a normal user CMD for later live checks |
| Worker 409 on startup | ID already registered; reconnection is unsupported; fresh master or a genuinely new test ID is required |
| Tasks remain pending | No eligible idle worker; confirm registered workers are actually running |
| Task stuck assigned/running after disconnect | Expected current recovery limitation; no redelivery/retries/heartbeat |
| Result 404 | Wrong ID, not an image task, not completed, or metadata lost after master restart |
| Upload 413/415/422 | Check file bytes, extension/MIME, decoded dimensions and operation parameters |
| LAN timeout | Check actual Wi-Fi IPv4, same network, Private firewall permission and router guest/client isolation |
| Faster worker does more tasks | Expected: round-robin skips busy workers; no adaptive scheduler is implemented |

Metadata is process-local and cleared at restart; stored files persist but are not rediscovered. Worker IDs are not authentication. Multipart parsing may spool uploads before application size limits apply. No database, adaptive scheduling, heartbeat, recovery or React UI is implemented. Record these limits separately from new regressions.

## 7. Blank teammate Pass/Fail checklist

Tester: __________  Date: __________  Revision: __________  Windows/Python: __________

Leave outcome cells blank until actually executed. Use Pass, Fail or Blocked with evidence; do not copy automated passes into manual outcomes.

| ID | Manual case | Pass/Fail/Blocked/Not Tested | Evidence / issue / retest |
| --- | --- | --- | --- |
| S1 | CMD setup, both environments and dependency checks | | |
| P1-1 | Health, empty/listed workers, registration and logs | | |
| P1-2 | Duplicate ID preserved; 409 documented in Swagger | | |
| P1-3 | Invalid/malformed registration and trimmed values | | |
| P1-4 | Actual worker hostname, failure exit and duplicate startup | | |
| P2-1 | Pending task batch, unique IDs and task inspection | | |
| P2-2 | Registration dispatch, one active task and round-robin | | |
| P2-3 | First poll delivers once; repeat poll returns null | | |
| P2-4 | Start/completion ownership and invalid transitions | | |
| P2-5 | Duplicate completion unchanged; failure terminal | | |
| P2-6 | Two local workers process dummy success/failure | | |
| P2-7 | Invalid task batches create no partial tasks | | |
| P2-8 | Stop/restart behavior and known recovery limitations | | |
| P3-1 | JPG + PNG multi-upload; one task per image | | |
| P3-2 | Grayscale visual output and dimensions | | |
| P3-3 | Resize exact dimensions | | |
| P3-4 | Gaussian blur visual output | | |
| P3-5 | Edge detection visual output | | |
| P3-6 | View inline and download completed PNG | | |
| P3-7 | Owner-only input; result state/ownership validation | | |
| P3-8 | Wrong/corrupt output rejected; completion cannot bypass upload | | |
| P3-9 | Same result idempotent; different result cannot replace | | |
| P3-10 | Upload byte/pixel/count/type/animation limits | | |
| P3-11 | Atomic rejected batch, distinct filenames and safe storage | | |
| P3-12 | Explicit image failure and missing/unfinished result | | |
| LAN-1 | Second laptop registration and dummy execution | | |
| LAN-2 | Image executes remotely without copying input/shared paths | | |
| LAN-3 | Downloaded LAN output and device/network evidence | | |

For a failure, record exact commands, request body/file, expected/actual HTTP response, task/worker IDs and logs. Exclude secrets and private image data from committed reports. Append actual manual results and later retests to TEST_RESULTS.md; preserve this procedure as the repeatable reference.

## 8. Phase 4: resource monitoring and heartbeats — NOT YET EXECUTED

These are pending teammate procedures, not reported passes. Preserve earlier Phase 1-3 checks; repeat their regressions after this phase. No LAN or live TCP Phase 4 result is claimed.

### Start the master and two monitored workers

Stop older project processes with Ctrl+C. Window A (CMD):

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "WORKER_TIMEOUT=10"
set "TIMEOUT_CHECK_INTERVAL=1"
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

Window B:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=phase4-worker-1"
set "POLL_INTERVAL=1"
set "TASK_DELAY=15"
set "HEARTBEAT_INTERVAL=3"
set "HEARTBEAT_HTTP_TIMEOUT=2"
worker\.venv\Scripts\python.exe worker\worker.py
```

Window C: repeat B with `WORKER_ID=phase4-worker-2`. Unique IDs are required. Defaults are heartbeat interval 3 seconds, heartbeat connect/read timeout 2 seconds each, master timeout 10 seconds and sweep interval 1 second. Intervals are finite positive numbers; existing TASK_DELAY accepts zero. Existing task HTTP timeout remains connect 3.05/read 10 seconds. HEARTBEAT_INTERVAL is the wait after a heartbeat finishes; slow requests add time. Set the master timeout above the expected interval and latency.

### P4-1: API schema, metrics and timestamps

Window D:

```bat
curl.exe -i http://127.0.0.1:8000/workers
curl.exe -i http://127.0.0.1:8000/workers/phase4-worker-1
timeout /t 4 /nobreak
curl.exe http://127.0.0.1:8000/workers/phase4-worker-1
```

Expected: 200; records retain worker_id/hostname and add `last_seen`, `status`, `cpu_percent`, `ram_percent`, `available_ram_mb`. For example (numbers vary):

```json
{"worker_id":"phase4-worker-1","hostname":"YOUR-PC","last_seen":"2026-11-19T10:00:03Z","status":"online","cpu_percent":12.5,"ram_percent":45.0,"available_ram_mb":4096.0}
```

last_seen should advance roughly every 3 seconds on an idle local network; it is server UTC receipt time, not the worker's clock. Timeout decisions use elapsed monotonic server time. Resource errors produce null metrics without invalidating the heartbeat. Available RAM uses MiB (1024² bytes), despite the field's MB name. The initial nonblocking CPU sample may be 0; later values reflect utilization since the previous sample. Compare approximately with Windows Task Manager; do not require identical instantaneous values. Observe normal use of the machine rather than creating an uncontrolled load test. Unknown worker detail returns 404. Tokens must never appear in GET worker responses.

Swagger `/docs` exposes the heartbeat schema/example, status ranges and session headers. Metrics percentages must be finite numbers in 0-100; available RAM must be finite and nonnegative. Null denotes unavailable. Extra keys and malformed timestamp return 422. The optional client timestamp is informational and cannot postpone timeout.

### P4-2: periodic heartbeats during task execution

With B/C running, submit dummy tasks using earlier commands and observe a 15-second dummy task. Fetch worker detail before/during/after execution: last_seen advances while the task is running and status stays online, despite the 10-second timeout. Task output and polling should continue independently.

Also submit a multi-image batch with the Phase 3 commands. Watch task transitions and worker last_seen together. Image work is real OpenCV work; TASK_DELAY does not slow image operations, and small images may finish between heartbeat samples. Use several detailed permitted images if needed; record observed durations and avoid claiming a short task proves long-duration continuity. The automated synchronization test separately verifies heartbeats while processing is blocked.

### P4-3: timeout without read-triggered detection

Stop idle worker B with Ctrl+C. Do not call `/workers` for 12 seconds:

```bat
timeout /t 12 /nobreak
curl.exe http://127.0.0.1:8000/workers/phase4-worker-1
```

Expected offline with last_seen unchanged and the most recent metrics retained (now stale). The background lifespan task expires it even if nobody calls GET; the controlled-clock automated test establishes this without relying on reads. Exactly 10 seconds is still online; strictly more than 10 expires, normally observed within one further sweep interval. Normal request delays/OS scheduling can add jitter. Stopping a worker does not immediately unregister it.

Submit more tasks while worker 1 is offline and worker 2 is idle: only the online eligible worker receives new work. CPU/RAM values are never used to rank or assign workers.

### P4-4: restart and reconnect without identity hijacking

Restart B using its same commands and ID **after it is offline**. Expected registration succeeds, status becomes online, metrics reset to null until the next heartbeat, and a new private session token is issued. An idle worker with no old active task can process new tasks. Starting another process with the same ID while B is online must still return 409 and leave B unchanged.

To test interrupted work, use a fresh master and one worker with TASK_DELAY=15. Submit one dummy task, wait for running, then stop the worker. After timeout, verify the task is still running with the original assignment/attempt_count (1). Restart that ID. Its old task must not be started/completed/failed by the new session; the task remains busy and stuck. A previous unpolled assignment may cause polling to return 409, stopping the restarted worker. No retry/requeue or automatic task takeover is expected. Reset the demonstration by restarting the master and workers; do not manually mutate registry internals.

### P4-5: explicit session and heartbeat negative requests

Use a fresh master with no running workers to isolate this case. Register via CMD and inspect the response **locally**:

```bat
curl.exe -i -X POST http://127.0.0.1:8000/workers/register -H "Content-Type: application/json" -H "X-Worker-Protocol: session-v1" -d "{\"worker_id\":\"session-test\",\"hostname\":\"manual-host\"}"
set "WORKER_SESSION=PASTE_PRIVATE_X_WORKER_SESSION_HEADER"
curl.exe -i -X POST http://127.0.0.1:8000/workers/heartbeat -H "X-Worker-Session: %WORKER_SESSION%" -H "Content-Type: application/json" -d "{\"worker_id\":\"session-test\",\"cpu_percent\":12.5,\"ram_percent\":45,\"available_ram_mb\":4096}"
```

Expected registration 201 with the original JSON identity body and private response header; heartbeat 200 with extended worker record. Send heartbeat promptly, before timeout. Do not paste real tokens into reports, screenshots or committed files. This hand-driven identity has no background sender.

Repeat promptly with CPU -1/101, RAM 101/string/bool, available RAM -1 or an extra field: expect 422 and unchanged last_seen. Send an unknown worker ID: 404. Missing or incorrect token for session-test: 401. After expiry, the correct old token gets 409; registration with session-v1 then issues a different token. The old token gets 401 after rotation. Replace WORKER_SESSION with the new header and repeat the valid heartbeat: 200. Clear it afterward with `set "WORKER_SESSION="`.

For a session-aware worker, attach this header to polling, task start/complete/fail, input download and multipart result upload. Without it those protected operations are rejected (image result structure validation may return 422 before the session check if the file is invalid). Registration response body is intentionally unchanged; GET worker records are extended. Legacy registrations without the protocol header preserve the earlier trusted-network behavior, but cannot reconnect or be upgraded. Manual Phase 1-3 workers need manual heartbeats or the longer timeout noted at the top of this guide.

### P4 troubleshooting and limits

| Symptom | Expected action / limitation |
| --- | --- |
| Null metrics | psutil sampling failed; heartbeat still works. Check worker warnings/permissions and later samples |
| First CPU value 0 | Nonblocking psutil baseline sample; check later heartbeats |
| Heartbeat warning / status offline | Check URL, HTTP latency, process health and timeout settings; no automatic registration/recovery loop |
| Restart returns 409 | Wait for offline; an online identity remains protected. Legacy IDs cannot reconnect |
| Restarted worker has no work or task-session 409 | Old task remains assigned/running; Phase 5 recovery is deliberately absent |
| 401 after master/worker restart | Token no longer matches; restart/register the worker explicitly; tokens are not persisted |
| TCP works but large task interrupted | Heartbeat is independent; task requests still have their existing HTTP timeouts |
| Worker shutdown delayed briefly | Heartbeat thread signals stop and joins up to connect+read timeout+1 second (5 seconds by default); Requests DNS/OS stalls can exceed nominal HTTP timeouts, so daemon-thread termination remains best effort |

Run one master process. No persistence, authenticated enrollment, adaptive scheduler or task recovery was added. Session tokens fence reconnecting workers; legacy enrollment is still trusted-network only. Heartbeat transport failures are logged and later scheduled heartbeats continue; task HTTP failures stop the task loop. Reconnection requires explicitly restarting a worker process, not an automatic reconnect loop.

For future two-laptop testing, use the existing LAN section, the same heartbeat variables and unique IDs. Check metrics/last_seen from both devices, interrupt the remote worker, wait for offline, then restart it. **LAN cases remain NOT YET EXECUTED.**

| ID | Phase 4 manual case | Pass/Fail/Blocked/Not Tested | Evidence / issue / retest |
| --- | --- | --- | --- |
| P4-1 | Online registry, resource metrics, timestamps and Swagger schemas | | |
| P4-2 | Heartbeat continuity during dummy and image work | | |
| P4-3 | Background offline timeout without intermediate GET requests | | |
| P4-4 | Offline worker excluded from new assignments | | |
| P4-5 | Idle offline reconnect; online duplicate blocked | | |
| P4-6 | Old session rejected for heartbeat/task/image updates | | |
| P4-7 | Interrupted task preserved; no retry/requeue after reconnect | | |
| P4-8 | Invalid metrics/configuration and nullable resource samples | | |
| P4-9 | Clean worker/master monitoring shutdown | | |
| P4-LAN | Metrics, timeout and reconnect across two laptops | | |

## 9. Phase 5 scheduling and recovery — NOT YET EXECUTED

No teammate manual, live TCP or LAN result is claimed here. Keep Pass/Fail fields blank until actual execution. Full policy/defaults are in [phase5.md](phase5.md).

### Same-laptop setup and mode comparison

Fresh master means stop project workers/master, then restart. Do not delete unrelated files. In CMD A:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "SCHEDULER_MODE=static"
set "MAX_TASK_ATTEMPTS=3"
set "METRICS_MAX_AGE=8"
set "FAIRNESS_MAX_SKIPS=5"
set "HISTORY_MIN_SAMPLES=3"
set "MIN_AVAILABLE_RAM_MB=128"
set "RAM_TARGET_MB=1024"
set "WORKER_TIMEOUT=10"
set "TIMEOUT_CHECK_INTERVAL=1"
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

CMD B and C (use worker-1 in B and worker-2 in C):

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=worker-1"
set "HEARTBEAT_INTERVAL=3"
set "HEARTBEAT_HTTP_TIMEOUT=2"
set "POLL_INTERVAL=1"
set "TASK_DELAY=15"
worker\.venv\Scripts\python.exe worker\worker.py
```

Wait for both to appear online. Submit the same dummy/image workloads from earlier sections and inspect:

```bat
curl.exe http://127.0.0.1:8000/scheduler
curl.exe http://127.0.0.1:8000/tasks
```

Repeat with a fresh master and `set "SCHEDULER_MODE=adaptive"`. Preserve workload/count and record actual CPU/RAM/history and assignments; do not infer speedup from task counts. Set `TASK_ID` to a real returned ID and inspect:

```bat
set "TASK_ID=PASTE_REAL_TASK_ID"
curl.exe http://127.0.0.1:8000/tasks/%TASK_ID%/attempts
```

Expected mode/configuration, loads 0/1, mean completion samples, and task attempt history containing mode, score, assignment_reason, worker and timestamps. A score can be null for fallback/static/fairness decisions without a fresh score. No private tokens should appear in these public responses.

### Controlled uneven metrics, fallback and fairness

Same-laptop workers observe the same whole-host CPU/RAM, so two local processes do not provide a controlled heterogeneous-hardware comparison. For a deterministic manual policy check, use a fresh adaptive master with no automatic workers. Register two identities with session-v1 as in Phase 4, retain both private tokens locally, and send manual heartbeats promptly (or temporarily use WORKER_TIMEOUT=3600 and METRICS_MAX_AGE=3600 for this hand-driven exercise):

```bat
set "SESSION_A=PASTE_FIRST_PRIVATE_SESSION"
set "SESSION_B=PASTE_SECOND_PRIVATE_SESSION"
curl.exe -X POST http://127.0.0.1:8000/workers/heartbeat -H "X-Worker-Session: %SESSION_A%" -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\",\"cpu_percent\":95,\"ram_percent\":95,\"available_ram_mb\":128}"
curl.exe -X POST http://127.0.0.1:8000/workers/heartbeat -H "X-Worker-Session: %SESSION_B%" -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-b\",\"cpu_percent\":5,\"ram_percent\":10,\"available_ram_mb\":4096}"
```

Submit one task: expect manual-b selected absent an overdue fairness counter. If both eligible workers have no full/fresh metrics, expect recorded round-robin fallback. If some fresh samples exist, stale/missing samples are excluded; all fresh workers below MIN_AVAILABLE_RAM_MB leaves work pending. Repeatedly complete one task at a time while both stay eligible: a consistently lower-scoring worker eventually receives the fairness decision after configured skips. Use polling tokens for start/finish, never public task data as a credential. These supplied metrics are synthetic policy inputs, not measured hardware load.

For real uneven load on two laptops, use normal foreground applications on only one laptop and observe its metrics, without uncontrolled stress programs. Do not expect deterministic values or claim a benchmark result. Cold-start history uses a neutral .5 until HISTORY_MIN_SAMPLES successes; metric changes must not move a currently running task.

### Timeout/requeue/reassignment during dummy or image work

Restore default timeouts and start a fresh static master plus two real workers. Submit a batch; for a deterministic slow stop case use TASK_DELAY=15 dummy work. Wait for a task to be running, identify its worker, then Ctrl+C that worker. In D:

```bat
timeout /t 12 /nobreak
curl.exe http://127.0.0.1:8000/workers
curl.exe http://127.0.0.1:8000/tasks/%TASK_ID%
curl.exe http://127.0.0.1:8000/tasks/%TASK_ID%/attempts
```

Expected: offline old worker; first attempt reason heartbeat_timeout; task pending if nobody else is eligible, or assigned/running on the remaining worker; attempt count increments only on a new assignment. Eventually expect completed output after the second worker finishes. No duplicate task IDs or duplicate queue ownership. Repeated waits/status reads do not create extra attempts.

Repeat with a permitted multi-image batch, watching worker messages to stop during an actual image task. Small images may finish before Ctrl+C: if so, record that the interruption was not achieved and repeat rather than declaring recovery passed. TASK_DELAY does not slow images. Keep original inputs only on the master. After reassignment the other worker must download bytes and produce a valid viewable/downloadable PNG. Inputs must remain present across retries; stale outputs must not replace the accepted file.

Restart the stopped worker with the same ID after offline detection. Registration should rotate its session. It may receive new assignments; it must not reuse a previous session or assignment token. The same task ID can return only as a newly counted generation. An online duplicate ID remains rejected with 409.

### Stale mutation/output and retry-limit checks

For controlled credential tests, register a manual session-aware worker and poll one task. Record `assignment_token` locally as ATTEMPT_OLD, without putting it into reports. Send start with both headers. Stop heartbeats and wait for timeout; register again or let another worker take a new attempt. Try start/complete/fail and image input/result operations using old headers: expect 401 for a stale session or 409 for invalid ownership/generation. Use a structurally valid result image to isolate generation validation; an invalid image may fail earlier with 422.

Current-generation example (substitute actual session/attempt values):

```bat
set "WORKER_SESSION=PRIVATE_CURRENT_SESSION"
set "TASK_ASSIGNMENT=PRIVATE_CURRENT_POLL_TOKEN"
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%TASK_ID%/start -H "X-Worker-Session: %WORKER_SESSION%" -H "X-Task-Assignment: %TASK_ASSIGNMENT%" -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\"}"
curl.exe -i -X POST http://127.0.0.1:8000/tasks/%TASK_ID%/fail -H "X-Worker-Session: %WORKER_SESSION%" -H "X-Task-Assignment: %TASK_ASSIGNMENT%" -H "Content-Type: application/json" -d "{\"worker_id\":\"manual-a\",\"error\":\"temporary test error\",\"retryable\":true}"
```

For an automatic deterministic budget test on a fresh master with real workers:

```bat
curl.exe -X POST http://127.0.0.1:8000/tasks -H "Content-Type: application/json" -d "{\"tasks\":[{\"operation\":\"dummy\",\"payload\":{\"fail\":true,\"retryable\":true}}]}"
```

With MAX_TASK_ATTEMPTS=3 expect exactly three assignments, retry/retry/failed history and terminal failed. TASK_DELAY=15 makes this take about 45 seconds plus polling; use TASK_DELAY=.5 on freshly launched workers for a shorter check. With retryable omitted or false, dummy/processing failure is terminal after one attempt. Max attempts 1 disables retry. Missing assignment token on modern task updates returns 409. Identical completed result uploads with current credentials remain idempotent; changed/stale bytes cannot alter the accepted result. Verify download contents and file count before/after rejected uploads.

### Shutdown, troubleshooting and LAN checks

- No online worker: work stays pending; registration/heartbeat/sweep later triggers distribution. Legacy-only capacity cannot execute a secure retry, and adaptive mode excludes legacy identities.
- Retryable pending work may wait behind a recovered FIFO head that needs a session-aware worker. Use updated workers, not registry mutation.
- Worker network error: a reachable master may accept a retryable failure report; otherwise task-loop exit stops heartbeats and timeout initiates recovery. Do not manually send duplicate claims to compensate.
- Master restart loses queue, attempt history and credentials; existing files do not constitute recovered tasks. Restart workers and resubmit explicitly. This is not persistence testing.
- For LAN, use the existing two-laptop setup with master `--host 0.0.0.0`, the actual LAN MASTER_URL and unique IDs. Compare static/adaptive decisions with recorded metrics, stop the remote worker during work, observe reassignment locally, restart remotely and download the result. Do not copy input files onto the remote worker. No LAN pass is claimed.
- Clear private token variables after tests. Do not commit secrets, test images or outputs.

| ID | Phase 5 manual case (NOT YET EXECUTED) | Pass/Fail/Blocked/Not Tested | Evidence / retest |
| --- | --- | --- | --- |
| P5-1 | Static baseline preserved and mode/configuration API correct | | |
| P5-2 | Adaptive low/high CPU/RAM selection with synthetic metrics | | |
| P5-3 | Stale/missing metrics, cold-start and low-memory behavior | | |
| P5-4 | Fairness, busy/offline exclusion and no running migration | | |
| P5-5 | Assigned/running timeout, requeue and reassignment | | |
| P5-6 | Image bytes preserved through retry and valid completed PNG | | |
| P5-7 | Old session/generation rejected; accepted output unchanged | | |
| P5-8 | Permanent failure and exactly MAX_TASK_ATTEMPTS for retryable failure | | |
| P5-9 | Duplicate completion/recovery does not duplicate work | | |
| P5-10 | No-worker pending queue, shutdown/restart limitations | | |
| P5-LAN | Two-laptop distribution, disconnect/restart and result transfer | | |

## 10. Phase 6 React dashboard — NOT YET EXECUTED

All procedures below are pending teammate manual tests. Existing Phase 1-5 instructions remain above. Do not copy automated passes into this checklist. Capture actual outcomes, revision, browser/version, screenshots and console/network evidence in TEST_RESULTS.md, excluding private tokens/images.

### Localhost: install and start four processes

Terminal A (master):

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "SCHEDULER_MODE=static"
set "CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173"
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

Terminal B (worker 1):

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=dashboard-worker-1"
set "HEARTBEAT_INTERVAL=3"
set "POLL_INTERVAL=1"
set "TASK_DELAY=15"
worker\.venv\Scripts\python.exe worker\worker.py
```

Terminal C: repeat B with WORKER_ID=dashboard-worker-2. Terminal D (frontend):

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing\frontend
npm ci
set "VITE_MASTER_URL=http://127.0.0.1:8000"
npm run dev
```

Use npm install for initial setup if a lockfile is absent; the current project includes one. Stop on dependency errors and record setup as blocked. Existing Python environments/requirements are prepared using section 1. Open http://127.0.0.1:5173 in a browser. Development binds loopback, strict port 5173. An occupied port is an error, not an automatic switch. Change the origin configuration if deliberately using another frontend port. Optional frontend/.env uses the same VITE_MASTER_URL; do not overwrite an existing file. Restart Vite after configuration changes. Backend CORS changes require master restart.

### P6-1: overview, empty and error states

Start with a fresh master and frontend only. Expect real zero counts and no workers/tasks/results, not example data. Navigate every section and confirm helpful empty states. With the master stopped, expect a loading/connection error and no fabricated counts. Start the master and observe reconnect plus a fresh snapshot. If prior data was displayed, a connection error must clearly identify the retained snapshot as old. Screenshot initial empty overview and the error notice.

After starting B/C, compare overview online/offline counts and Workers cards with GET /workers in Swagger. Compare task totals and each pending/assigned/running/completed/failed count with GET /tasks. Capture overview and worker-card screenshots. Scheduling mode must match GET /scheduler; there is no runtime mode toggle. Restart all processes with SCHEDULER_MODE=adaptive and verify the explanation/configuration changes. Do not interpret the UI as a performance improvement measurement.

### P6-2: uploads and operation parameters

Open Image processing. Select 2-3 real JPG/PNG files with visible detail. Choose grayscale and submit. Expect a clear in-flight label, then returned task IDs and tracking buttons; queued tasks are not labeled completed on upload. Track a task, observe current assignment and attempt history, then navigate Results when completed.

Repeat resize with exact width/height (e.g. 320×240), Gaussian blur with odd kernel 5 and edge detection with thresholds 100/200. Confirm only appropriate fields appear. Compare the completed visual output and resize dimensions. Upload more than 20 files, a text file, empty file, >10 MiB file, oversized decoded image, invalid resize values, even kernel and reversed thresholds: expect client or backend error without a success notice. The file picker may filter unsupported extensions; choose an invalid file through browser tools only if needed, without altering the application. Browser decoding cannot replace backend verification; a corrupt disguised PNG should be rejected.

Capture upload fields, validation message, created IDs and one result per operation. Do not include private source images in committed screenshots. Upload uses Fetch status, not byte percentage.

### P6-3: worker metrics, task search and history

In Workers, verify ID, hostname, online/offline status, CPU/RAM meters, available MiB and local display of last_seen. Null metrics say Unavailable; old/offline values are labeled stale. Compare approximately with Task Manager (sampling times differ). Task table search must match task ID, operation or worker; status filters include Assigned separately from Pending/Running. Open details and compare attempt history/reasons against GET /tasks/{id}/attempts. Multiple retries/reassignment should update while details are open, without changing task ID.

Capture task filters, detailed history and stale worker metrics. Results must include completed images only, excluding dummy/pending/failed tasks. Preview opens the HTTP result, download uses the existing attachment endpoint, and missing results show an error/placeholder rather than a broken local filesystem link. Originals are deliberately not available because the existing input API is worker-only. Inspect Network/storage to confirm the frontend never requests worker session/assignment credentials or stores them in localStorage/sessionStorage.

### P6-4: disconnect, recovery and live-update transport

Submit dummy work with TASK_DELAY=15. Stop its owning worker while running and observe last_seen stop, offline status after timeout, attempt history with heartbeat_timeout and reassignment to the remaining worker. Repeat during a real image operation if its execution is long enough; a tiny image may finish too quickly, which is not a recovery pass. The valid new result must become downloadable, with original task ID and increased attempts. Restart the old worker after offline detection and verify online status/new assignments. Use Phase 5 procedures for stale-result rejection; the dashboard does not hold the private credentials needed to submit those mutations.

Open browser DevTools (F12), Network, and filter WS. Expect one active /ws/dashboard socket and changed-state snapshot messages, with no private token fields. Initial GET /workers, /tasks, /scheduler is normal. Frames arrive only when state changes, not as invented activity. Block the WebSocket URL using DevTools request blocking and reload: expect Polling fallback and public GET refreshes around every five seconds. Remove blocking: socket attempts back off 1/2/4/8/16/30 seconds and live state refreshes after reconnection. There should be no accumulating duplicate sockets/poll timers. Selected task detail also fetches the existing attempt endpoint when task status/attempt changes.

Stop the master, inspect the UI error/last-snapshot notice, restart and confirm cleared in-memory state is reflected. Console must have no unhandled exceptions; transport errors during deliberate outages should be explained by UI status. CORS errors usually mean VITE_MASTER_URL and the exact frontend origin are mismatched. A working Swagger page alone does not prove browser CORS is configured.

### P6-5: responsive/accessibility and production check

Use browser responsive mode at approximately 390px and 1440px. Navigation, labels and primary actions should remain usable; tables may scroll horizontally. Keyboard-tab through navigation, upload, filters, task buttons and downloads: visible focus and accessible labels are required. Test loading/empty/error states at both widths. Capture screenshots of desktop overview, mobile navigation, tasks/detail and results. No screenshots or browser QA have been generated automatically in this implementation.

In frontend CMD run npm test and npm run build. Expect test counts/exit statuses recorded independently from manual outcomes. The initial dependency tree has unresolved development-tool advisories (1 moderate, 2 critical) in Vitest/tinypool/mocker. A patched Vitest upgrade was attempted but registry DNS failed; review a compatible patched version, update package/lock together and rerun tests/build/npm audit when access is available. Do not claim the audit passed or expose test tooling publicly. Production build success does not erase development-tool advisories.

### Separate two-laptop LAN dashboard scenario — NOT YET EXECUTED

Use the trusted-network steps in section 5, with actual master IPv4 (example 192.168.1.10). Stop local processes first. On the master laptop:

```bat
set "CORS_ALLOWED_ORIGINS=http://192.168.1.10:5173"
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 0.0.0.0 --port 8000
```

In a separate frontend CMD on that laptop:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing\frontend
set "VITE_MASTER_URL=http://192.168.1.10:8000"
npm run dev -- --host 0.0.0.0
```

On laptop 2 open http://192.168.1.10:5173 and run its worker with MASTER_URL=http://192.168.1.10:8000 and a unique ID. Permit only the intended Private-network Python/Node ports when Windows asks; do not disable the firewall globally. Never use 127.0.0.1 as the remote destination or put 0.0.0.0 in VITE_MASTER_URL. Confirm the browser Origin exactly matches the master CORS list (no trailing slash). If frontend is hosted on a different laptop, use that frontend laptop's actual origin in the allowlist.

Upload through the dashboard, observe both workers, interrupt/restart the remote worker and download completed output. No shared input directory should be needed. Capture devices/IPs, browser console/network evidence and task/attempt IDs. Do not claim LAN pass until actually executed. Stop exposed dev services afterward and return local binding to loopback.

| ID | Phase 6 manual case | Pass/Fail/Blocked/Not Tested | Evidence / retest |
| --- | --- | --- | --- |
| P6-1 | Empty/loading/error/retained-snapshot states; real counts | | |
| P6-2 | Multi-upload and all operation parameters/validation | | |
| P6-3 | Created IDs, task filtering, details and retry history | | |
| P6-4 | Worker resource/status/heartbeat and stale/null display | | |
| P6-5 | Result preview/download/missing result; no local paths | | |
| P6-6 | Read-only static/adaptive configuration and stored events | | |
| P6-7 | Worker timeout/reassignment while dashboard stays open | | |
| P6-8 | WebSocket disconnect/backoff/poll fallback; no duplicate subscriptions | | |
| P6-9 | No worker credentials in frontend storage/events/public state | | |
| P6-10 | Desktop/mobile keyboard accessibility and screenshots | | |
| P6-11 | Build/tests and development dependency advisory follow-up | | |
| P6-LAN | Browser + worker on second laptop; uploads/recovery/results | | |

## 11. Phase 7 benchmarking — NOT YET EXECUTED

These manual/experimental cases are pending, not performance results. Preserve Phases 1-6 checks above. See [phase7.md](phase7.md) for exact boundaries, formulas and validity rules. Do not benchmark production workloads, automatically kill workers or delete unrelated tasks. The standalone runner does not alter scheduler mode or hold worker credentials.

### P7-1: prepare inputs, environment and isolated processes

In CMD at the repository root, using the existing worker environment:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.workload --directory benchmarks\workloads\small-42 --profile small --seed 42
worker\.venv\Scripts\python.exe -m benchmarks.workload --directory benchmarks\workloads\medium-42 --profile medium --seed 42
worker\.venv\Scripts\python.exe -m benchmarks.workload --directory benchmarks\workloads\large-42 --profile large --seed 42
copy benchmarks\environment.example.json benchmarks\environment.json
```

Choose new directories rather than overwriting existing data. Expected manifests contain seed, provenance, sorted names, dimensions and input SHA-256 hashes. Defaults are 6 small, 24 medium and 60 large images. Optional --count/--width/--height/--format override these; retain the exact same directory across modes. These are synthetic RGB rectangles, not a photo dataset. A separate real-photo folder can be used with recorded provenance.

Edit every REPLACE value in environment.json. RAM MiB must be a positive number. Worker IDs must match the commands below; hostname must match actual registration. Record both workers' physical-device labels, CPU, RAM, Python/OpenCV versions, master hardware, Git revision, network kind/band/router/traffic and power/background application conditions. Use the identical environment file, including both hardware entries, for all three modes. Do not put passwords or session tokens into metadata. Record whole-host measurements and distinguish multiple processes on one laptop from multiple physical laptops.

Stop only your project processes with Ctrl+C and start a fresh master. Leave dashboard and unrelated uploads stopped for the experiment. Configure non-mode scheduler weights, timeouts and retries identically across all modes. Set VITE/frontend aside so polling load does not differ between trials.

### P7-2: single-device baseline

CMD A:

```bat
set "SCHEDULER_MODE=static"
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

CMD B (only this worker online):

```bat
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=bench-1"
worker\.venv\Scripts\python.exe worker\worker.py
```

Wait for regular heartbeats, then CMD D:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.runner --master-url http://127.0.0.1:8000 --mode single --workers bench-1 --workload benchmarks\workloads\small-42 --operation grayscale --environment benchmarks\environment.json --trials 3 --warmups 1 --timeout 300 --output benchmarks\results
```

Expected: one warmup plus three measured run UUID folders, each mapping exactly one task per image. Successful baseline work is real JPG/PNG HTTP processing. Worker 2 being online must cause a preflight error, not silently contaminate the baseline. Any unrelated unfinished tasks must also cause refusal. A successful process exit is not proof of a speedup; inspect each run.valid, issues, successful/failed counts and output hashes.

### P7-3: static and adaptive distributed trials

Stop/restart the project master/workers; do not reuse an active mixed workload. Start static master, start bench-1 and bench-2 in separate terminals with the same MASTER_URL and distinct IDs. Repeat the baseline command with:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.runner --mode static --workers bench-1,bench-2 --workload benchmarks\workloads\small-42 --operation grayscale --environment benchmarks\environment.json --trials 3 --warmups 1 --timeout 300
```

Restart again with `set "SCHEDULER_MODE=adaptive"`, then start the same two workers and run:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.runner --mode adaptive --workers bench-1,bench-2 --workload benchmarks\workloads\small-42 --operation grayscale --environment benchmarks\environment.json --trials 3 --warmups 1 --timeout 300
```

Expected: no runtime scheduler change; mismatch produces refusal. The distributed online worker set must be identical in static/adaptive runs. Reuse input hashes/operations/parameters, record background conditions, and never silently discard a failed trial. Workload tasks can be assigned differently but must retain one task per image. Repeat all three modes for medium/large and operations:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.runner --mode adaptive --workers bench-1,bench-2 --workload benchmarks\workloads\medium-42 --operation resize --params "{\"width\":640,\"height\":480}" --environment benchmarks\environment.json
```

For blur use operation gaussian_blur/params kernel_size=5; edges use edge_detection/threshold1=100/threshold2=200. Separate operations form separate comparison groups. Do not pool datasets/parameters/worker hardware. Rotate the mode order in further labeled experiment blocks to investigate cache/thermal/order effects; default warmup/repetition does not eliminate them.

### P7-4: inspect data, graphs and formulas

```bat
worker\.venv\Scripts\python.exe -m benchmarks.report --source benchmarks\results --output benchmarks\reports\experiment-01
```

Expected: report.md comparison table, summary.json, trials.csv, tasks.csv, resources.csv and six SVG charts. Pick a new output directory for every report. Open Markdown/CSV/JSON in appropriate local tools and SVGs in a browser. Resources graph shows whole-host last-reported samples, with solid CPU/dashed RAM and client elapsed seconds; repeated heartbeat values are not independent high-frequency samples. Hover series for run/worker identity. Per-run JSON retains raw task snapshots and history/retry reasons. Confirm warmup=true records stay in exports but not means.

Manually recompute successful images / batch elapsed seconds. Then use mean single elapsed / mean distributed elapsed for speedup and divide by allocated participating worker count for efficiency. At least three clean matched trials and one unambiguous baseline are required; invalid trials or mismatched workers prevent comparison. N/A is not zero. Mean/median/sample SD use valid measured trials, and invalid counts remain visible. Confirm configured pool count separately from executing_worker_ids; do not divide by a smaller post-hoc number merely to improve efficiency.

Batch time begins before uploads and ends when all tasks are observed terminal; result downloads/validation are outside this time and inside client_total_seconds. Queue/assigned-to-start/end-to-end times derive from master timestamps. Execution_and_transfer_seconds includes input/output HTTP, OpenCV and validation; pure worker-only CPU processing time is unavailable. Do not label it as such. Retain the same poll interval (default 1 second) across modes and acknowledge completion-detection overhead.

Capture final revision, metadata, command lines, all run UUIDs, report tables/graphs, successful image-output evidence and any failures for the final project report. No example/test measurements may be presented as observed experiments. A lower adaptive time in one trial is not a general performance claim.

### P7-5: fault, contamination, timeout and cancellation cases

- Start an unrelated unfinished task before a trial: expect preflight rejection and no benchmark upload. Start unrelated work during a trial: expect invalid/partial record with isolation issue.
- Stop an expected worker during real image execution (small images may finish too fast; record an unsuccessful interruption honestly). Expected offline/mismatched topology and/or retry history makes the trial invalid for clean speedup, but raw observations remain. Remaining tasks are not deleted; inspect GET /tasks, then reset only your own isolated experiment explicitly.
- Use a deliberately short positive --timeout to exercise timeout handling. Expect partial/invalid JSON and possibly still-running server tasks. HTTP/DNS/OS stalls may outlast the nominal deadline; record actual wall time. Ctrl+C during a trial records cancelled/invalid state, without terminating workers. Cancellation during preflight creates no measured trial because submission has not begun.
- Disconnect the master/network during upload. A POST may have succeeded remotely even if its response was lost: record uncertain submission and inspect server tasks before a new run. Never replay blindly or treat unknown task count as success.
- Change the input image after manifest inspection or duplicate/corrupt outputs: expect invalid success criteria, not a valid comparison. Existing assignment fencing still prevents stale worker results from replacing accepted output.
- Retry/failed trials remain in CSV/JSON and cause speedup N/A. Do not delete them merely to generate a favorable comparison. New clean experiments need a new label/report, with the earlier failure retained.

### P7-6: separate LAN evaluation

First complete the earlier two-laptop connectivity/image checks. No LAN benchmark is claimed as performed. Start a master bound to 0.0.0.0 on a trusted Private network, use its actual Wi-Fi/wired IPv4 in --master-url and remote MASTER_URL, and register exactly bench-1/bench-2. Do not use 0.0.0.0 as a destination or copy source images to the remote worker. Keep source benchmark workload on the benchmark-client machine and use real HTTP transfers.

Create metadata with distinct physical_device labels and accurate network details; do not mix loopback and LAN experiments under one metadata label. Run the same baseline/static/adaptive protocol with separate restarts and repeat counts. Test remote-worker disconnect and preserve invalid trial evidence. Record latency/other network traffic qualitatively unless actually measured. Master on the baseline laptop adds local contention; report it explicitly. Never claim distributed/adaptive is faster without complete measured results supporting that specific setup.

### Troubleshooting and remaining issues

| Symptom | Interpretation/action |
| --- | --- |
| Mode mismatch | Restart an isolated master in required startup mode; no runtime toggle |
| Expected online workers mismatch | Stop unintended project workers or wait for expected registrations/heartbeats; do not silently change the intended pool |
| Metadata/hostname refusal | Replace template placeholders with observed hardware; do not invent specs |
| Comparison N/A | Inspect invalid counts, >=3 trials, exact workload/config/environment group, baseline uniqueness and distributed worker set |
| Deadline exceeded | Preserve partial record; check active server tasks before rerun |
| WinError 10013 | Earlier socket restriction remains open; ASGI unit tests are not live benchmark passes |
| npm development audit findings | Rechecked: 1 moderate/2 critical; compatible upgrade attempt still blocked by DNS, not fixed |

| ID | Phase 7 manual/experiment case | Pass/Fail/Blocked/Not Tested | Evidence / retest |
| --- | --- | --- | --- |
| P7-1 | Seeded workloads, hashes/provenance and actual metadata | | |
| P7-2 | Single online-worker baseline, warmup plus >=3 trials | | |
| P7-3 | Same-workload static and adaptive distributed trials | | |
| P7-4 | CPU/RAM samples, task distribution, timing boundaries | | |
| P7-5 | CSV/JSON round trip, tables and actual-data SVGs | | |
| P7-6 | Independent speedup/efficiency/statistics calculation | | |
| P7-7 | Fault/retry/partial trials retained and comparisons invalidated | | |
| P7-8 | Contamination, cancellation and timeout safety | | |
| P7-LAN | Separate two-physical-laptop experiment with evidence | | |

## 12. Phase 8 final localhost/LAN handoff — NOT YET EXECUTED manually

### P8-1: prerequisites, installation and safe configuration

Objective: teammate Windows 10/11 CMD can install/run without username-specific edits. Prerequisites: source at a known revision, Python 3.13 baseline, Node >=22.14, npm/Git and package-index access. Open CMD in the repository:

```bat
python --version
node --version
npm --version
git --version
scripts\setup.cmd
if not exist master\.env copy master\.env.example master\.env
if not exist worker\.env copy worker\.env.example worker\.env
if not exist frontend\.env copy frontend\.env.example frontend\.env
scripts\start_master.cmd --check
scripts\start_worker.cmd --check
scripts\start_frontend.cmd --check
scripts\test_all.cmd
```

Expected: setup preserves configuration, creates missing separate environments, installs requirements/npm lockfile and changes no firewall settings. --check prints a command/status without starting services. Full verification exits 0 only when all stages pass, saving outputs/verification/UUID/results.json and UTF-8 logs. Check `echo %ERRORLEVEL%` immediately. Interrupted runs are not full passes. Capture versions, revision and verification UUID. Implementation-time checks against installed dependencies do not certify a clean-machine network install.

Environment files are simple KEY=value data, optional matching quotes and whole-line # comments. No shell evaluation, expansion or inline comments; terminal set values override files. Direct uvicorn/worker.py commands do not load the wrapper files. Actual .env files are ignored, examples contain no secrets, and dynamically issued tokens must never go in configuration/screenshots.

### P8-2: complete localhost integration

Objective: whole application works over real TCP/browser. Prerequisites: target setup, no unrelated project processes, real nonprivate JPG/PNG inputs. Four terminals: A runs scripts/start_master.cmd; B and C run scripts/start_worker.cmd after setting distinct WORKER_ID values; D runs scripts/start_frontend.cmd.

```bat
set "WORKER_ID=handoff-1"
scripts\start_worker.cmd
```

Use handoff-2 in C. Expected URLs: localhost:8000/health, /docs and dashboard http://127.0.0.1:5173. Follow Phases 1–6 cases: registration/metrics, all image operations, task progress/history/results, interruption/reassignment, stale result rejection and WS/poll reconnect. Current modern requests require private session and generation headers; use only local variables for those exercises. Legacy Phase 1-3 manual cases remain static first-attempt compatibility checks with the documented longer timeout.

Expected evidence: actual IDs, one task/image, valid PNG dimensions, updated metrics, bounded retries, real dashboard snapshots without credentials/local-file URLs. Screenshot desktop/mobile, Swagger and histories; do not expose tokens/private photos. API worker IDs containing separators now poll through path-aware routes, although simple unique IDs remain recommended for normal use.

### P8-3: complete two-laptop integration

Use TWO_LAPTOP_SETUP.md as the authoritative command list: A master/frontend/worker A, B worker B, actual IPv4 and explicit CORS/Vite URLs. Required inbound ports are 8000 on A and optional 5173 only for remote dashboard access; B workers need no inbound port. Check B health/registration, metrics, remote image byte transfer without shared files, interruption/reassignment/reconnect and valid result download. Check browser Console/Network/WS separately from curl/Swagger. Record physical device/network evidence in the execution template. All LAN cases remain pending until actually performed.

### P8-4: benchmark/demo/evidence package

Run Phase 7 experiments only after connectivity passes, using isolated modes, identical workload/metadata, warmup and >=3 measured trials. Retain failures and raw outputs. Helper commands:

```bat
scripts\benchmark_prepare.cmd --directory benchmarks\workloads\handoff-small --profile small --seed 42
scripts\benchmark_run.cmd --help
scripts\benchmark_report.cmd --source benchmarks\results --output benchmarks\reports\handoff-01
```

The report needs actual saved run files; an empty graph is not a measurement. Follow phase7.md for full run arguments. DEMO_GUIDE.md is a proposed 10–15 minute sequence, not an executed demo. Complete FINAL_CHECKLIST.md acceptance items only with evidence, defect IDs and retests. Preserve meaningful logs; do not commit generated datasets/reports or secrets.

### P8-5: safe diagnostics and known security limits

Run `python scripts/diagnose_network.py`, ipconfig, netstat and read-only Test-NetConnection from TWO_LAPTOP_SETUP.md. Record binds, connects, socketpair and DNS separately. Actual implementation probes passed ephemeral/8000/5173 binds, failed ephemeral connect with 10013, bounded socketpair to four seconds and failed DNS. Exact policy cause remains unknown; administrator review may be needed if a normal user CMD reproduces it. Do not disable firewall/antivirus or kill unrelated PIDs to force a pass.

Run npm audit and npm audit --omit=dev separately. Full dev audit currently has 1 moderate/2 critical findings; production-only reports zero. Compatible update was DNS-blocked; no forced upgrade is justified without compatibility/tests/build checks. In-memory reset, no authenticated enrollment/TLS, no quotas, structural output checks and best-effort HTTP deadlines remain documented limits, not hidden production guarantees.

| ID | Objective/procedure above | Pass/Fail/Blocked/Not Tested | Evidence / defect / retest |
| --- | --- | --- | --- |
| P8-1 | Fresh install, configuration precedence and relative scripts | | |
| P8-2 | Full localhost HTTP/browser/image/recovery integration | | |
| P8-3 | Full two-physical-laptop LAN integration | | |
| P8-4 | Benchmark/demo/report/evidence handoff | | |
| P8-5 | Read-only socket diagnosis, audit and security review | | |

No teammate case is marked Pass. Automated/programmatic checks and manual acceptance are separate categories. Append actual results to TEST_RESULTS.md only after execution, with the template and evidence links.
