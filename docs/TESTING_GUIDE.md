# Teammate testing guide — Phases 1, 2 and 3

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

| ID | Manual case | Pass/Fail/Blocked | Evidence / issue / retest |
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
