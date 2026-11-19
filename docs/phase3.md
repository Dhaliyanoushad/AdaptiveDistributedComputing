# Phase 3: distributed image processing

Phase 1 and Phase 2 endpoints and dummy tasks remain supported. Images use the same queue, static round-robin policy and one-active-task-per-worker rule. A batch creates one independent task per file. Workers receive bytes over HTTP and never use master-local filenames.

## Windows CMD setup

From the repository root, install dependencies in the existing separate environments:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
master\.venv\Scripts\python.exe -m pip install -r master\requirements.txt
worker\.venv\Scripts\python.exe -m pip install -r worker\requirements.txt
```

The master now uses Pillow for file validation; OpenCV processing stays in the worker. During implementation, network installation of Pillow failed. The already-installed Pillow 12.3.0 package and metadata were copied from the matching Python 3.13.2 worker environment into the master environment without replacing existing packages. Import and `pip check` succeeded. Normal setup should use pip as above.

Terminal 1:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=image-worker-1"
set "POLL_INTERVAL=1"
worker\.venv\Scripts\python.exe worker\worker.py
```

For another worker, open a third CMD terminal and repeat terminal 2 with `WORKER_ID=image-worker-2`. Run only one master process, without reload. Duplicate registration still returns 409; reconnection is not implemented. On another laptop, install its own worker environment and use the master laptop's LAN address as described in `phase1.md`; no shared disk is needed. No two-laptop test was performed.

## Image endpoints

| Endpoint | Contract |
| --- | --- |
| `POST /images/tasks` | Multipart `files` (repeated), `operation`, `params` (JSON string); returns 201 and an array of tasks |
| `GET /tasks/{task_id}/input?worker_id=...` | Actual input bytes for the registered assigned worker while assigned/running |
| `POST /tasks/{task_id}/result` | Multipart `worker_id`, `file` (PNG); validates and completes a running image task |
| `GET /tasks/{task_id}/result` | View completed PNG inline |
| `GET /tasks/{task_id}/result/download` | Download completed PNG attachment |

Use existing `/tasks`, `/tasks/{task_id}`, `/workers`, `/health` and `/docs` to inspect progress. Task payloads contain source dimensions and validated operation parameters, never local paths.

| Operation | `params` |
| --- | --- |
| `grayscale` | `{}`; produces an 8-bit grayscale PNG |
| `resize` | `{"width":640,"height":480}`; both required, 1-4096 each |
| `gaussian_blur` | `{"kernel_size":5}`; odd integer 1-99, default 5 |
| `edge_detection` | `{"threshold1":100,"threshold2":200}`; integers 0-255, low <= high |

Unknown parameters and unsupported operations are rejected. Resize uses exact requested dimensions (it does not preserve aspect ratio automatically). Gaussian blur uses OpenCV GaussianBlur with sigma 0; edge detection uses Canny after grayscale conversion. Output is always PNG. EXIF orientation is not applied; source raster dimensions are used. Alpha is discarded by OpenCV's color decode.

## Manual testing

Place two local JPG/PNG files in ignored `test_images/`. In a new CMD terminal, submit a batch:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
curl.exe -i -X POST http://127.0.0.1:8000/images/tasks -F "files=@test_images\one.jpg;type=image/jpeg" -F "files=@test_images\two.png;type=image/png" -F "operation=grayscale"
curl.exe http://127.0.0.1:8000/tasks
```

Change the filenames to real files. Expect one task per image, progressing through assigned, running and completed. Inspect worker terminal messages. In Swagger (`http://127.0.0.1:8000/docs`), **POST /images/tasks** supports selecting multiple files and entering an operation and JSON parameters. Try each operation using the table above. A CMD resize example:

```bat
curl.exe -X POST http://127.0.0.1:8000/images/tasks -F "files=@test_images\two.png;type=image/png" -F "operation=resize" -F "params={\"width\":320,\"height\":240}"
```

Copy a completed task ID, then view or download:

```bat
set "TASK_ID=PASTE_COMPLETED_TASK_ID"
curl.exe http://127.0.0.1:8000/tasks/%TASK_ID%
curl.exe -f http://127.0.0.1:8000/tasks/%TASK_ID%/result/download -o outputs\manual-result.png
```

Open `http://127.0.0.1:8000/tasks/YOUR_TASK_ID/result` in a browser. Check that grayscale/edges are grayscale, resize has requested dimensions, blur softens detail and edges outline high-contrast boundaries. The manual download command writes the specified local output filename; choose a different name if it already exists.

Negative checks in Swagger: upload text renamed `.png`, submit resize width 0 or an even blur kernel, request an unknown task, request another worker's input, complete an image via `/complete` without a file, or upload a wrong-sized result. Invalid image data/parameters return 422; unsupported MIME/extension returns 415; file byte limit returns 413; wrong owner/state returns 409; missing task/result returns 404. Rejected results do not complete the task. Preserve dummy regression behavior by submitting `{"tasks":[{"operation":"dummy"}]}` to **POST /tasks**.

## Storage, validation and failure behavior

- Accept 1-20 files per batch; 10 MiB maximum per encoded input/output; at most 4096 pixels per side and 16 million decoded pixels. Animated images are rejected. Files are decoded/verified, rather than trusting filename or MIME alone. The multipart parser may spool uploads before endpoint-level limits are checked; deploy this local prototype behind request-size limits before accepting untrusted large HTTP bodies.
- Inputs live in ignored `uploads/`; outputs in ignored `outputs/`. UUID filenames are generated by the master and opened exclusively. Client names are never used as filesystem paths. Failed batches remove their staged input files and publish no tasks.
- Output validation requires a running image task owned by the registered worker, a valid bounded PNG, expected dimensions and grayscale mode for grayscale/edges. This verifies output structure, not proof that an untrusted worker performed the correct algorithm. Tests separately check OpenCV results.
- Inputs are downloadable only by the assigned active worker. Worker IDs are identifiers, not authentication credentials. This remains a trusted-network prototype.
- Result file storage and completion occur under the store lock. Identical repeated result uploads by the owner are idempotent; different bytes cannot replace a completed result. `/complete` remains for dummy tasks only.
- Worker processing/decode/validation failures report `/fail`; HTTP transport failure stops the worker without retries. There is no recovery of interrupted assignments. Registries reset on master restart; files remain on disk but are not rediscovered. Cleanup of old files is manual.

## Automated tests and limits

Normal CMD commands:

```bat
master\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_master*.py" -v
worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -v
master\.venv\Scripts\python.exe -m pip check
worker\.venv\Scripts\python.exe -m pip check
```

The standard master command stalled here while Windows asyncio attempted to create its internal socketpair, before application execution. A test-only polling event loop avoids network sockets for ASGI tests:

```bat
master\.venv\Scripts\python.exe tests\run_master_tests.py
```

This runner tests HTTP request/response semantics directly through ASGI and file transfers, including multipart uploads and result downloads. Round-trip tests invoke the real OpenCV processor in the separate worker interpreter using transferred bytes. They do not start a live TCP server. This runner is not intended for application serving.

Observed results during implementation:

- In-process master runner: **29 tests passed**, including all 24 existing master tests and five image test methods covering all operations, atomic batch validation, safe filenames, invalid uploads/parameters, byte/pixel limits, ownership, state checks, completion-bypass rejection, duplicate result uploads and completed downloads.
- Worker discovery command: **19 tests passed**, including all 11 existing worker tests, exact OpenCV output checks, JPEG decoding, invalid data/parameters, HTTP download/upload request construction and reporting a processing failure.
- Both environments' `pip check` commands passed. `git diff --check` passed (only normal Windows line-ending warnings).
- Standard master discovery was attempted but could not finish because of the Windows asyncio socketpair restriction; its successful replacement was the explicit test-only runner above. No live TCP or two-laptop Phase 3 pass is claimed.

No adaptive scheduling, heartbeat monitoring, fault recovery, database or React frontend was added. A live TCP or two-laptop Phase 3 run remains a manual verification step.
