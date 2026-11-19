# API reference — implemented contracts

Default base http://127.0.0.1:8000; LAN uses Laptop A's actual IP. `/docs` and `/openapi.json` are the authoritative live HTTP schemas. WebSocket is described below, outside OpenAPI. URL-encode worker IDs; path-aware routes accept encoded separators. Prefer simple IDs such as laptop-a-1.

| Method / route | Input | Success |
| --- | --- | --- |
| GET /health | None | 200 `{"status":"ok"}` |
| POST /workers/register | JSON worker_id/hostname; X-Worker-Protocol: session-v1 for modern clients | 201 identity JSON + private X-Worker-Session response header |
| GET /workers | None | 200 array of records |
| GET /workers/{worker_id} | Encoded ID | 200 worker record |
| POST /workers/heartbeat | JSON worker_id, metrics, optional timestamp; modern session header | 200 worker record |
| POST /workers/{worker_id}/next-task | No required body; modern session header | 200 `{"task":<task-or-null>,"assignment_token":<private-or-null>}` |
| POST /tasks | JSON tasks array of dummy operations | 201 task array |
| GET /tasks | None | 200 task array |
| GET /tasks/{task_id} | UUID | 200 task |
| GET /tasks/{task_id}/attempts | UUID | 200 history array |
| POST /tasks/{task_id}/start | JSON worker_id + modern headers | 200 running task |
| POST /tasks/{task_id}/complete | Same, dummy only | 200 completed task |
| POST /tasks/{task_id}/fail | JSON worker_id/error/retryable + headers | 200 latest task, possibly reassigned |
| POST /images/tasks | Multipart files (repeated), operation, params JSON string | 201 one task per image |
| GET /tasks/{task_id}/input | worker_id query + headers | 200 actual bytes, application/octet-stream |
| POST /tasks/{task_id}/result | Multipart worker_id + file PNG + headers | 200 completed task |
| GET /tasks/{task_id}/result | UUID | 200 inline PNG |
| GET /tasks/{task_id}/result/download | UUID | 200 PNG attachment |
| GET /scheduler | None | 200 configuration/pending_count/worker load and history |
| WS /ws/dashboard | Allowed Origin, no private credentials | Initial/changed public snapshot frames |

Modern mutation/transfer headers are X-Worker-Session and X-Task-Assignment. Only registration/polling return them to the worker. They must never be included in frontend storage, query strings, logs, public snapshots or benchmark metadata. Legacy static requests retain old trust assumptions but cannot reconnect or receive secure retries.

## Schemas

Registration: strict trimmed strings worker_id (1-128), hostname (1-253), no extra keys. Response body stays `{"worker_id":"worker-1","hostname":"MY-PC"}`. Worker record adds last_seen (server UTC), status online/offline, cpu_percent/ram_percent (finite 0-100 or null), available_ram_mb (finite >=0 MiB or null). Optional client heartbeat timestamp is informational, not timeout authority. Percent bools/strings/NaN rejected.

Dummy POST /tasks: `{"tasks":[{"operation":"dummy","payload":{}}]}` with 1-1000 tasks. Only dummy is accepted here; images use the multipart endpoint. Failure error is strict trimmed 1-500 characters; retryable is strict boolean, default false. Dummy payload fail=true simulates failure, retryable=true requests bounded retry.

Task fields: task_id, operation, payload, status, assigned_worker, attempt_count, created_at, updated_at, assigned_at, started_at, completed_at, failed_at, error, attempt_history. Lifecycle timestamps are UTC/null as applicable. States: pending → assigned → running → completed/failed, with recoverable attempts returning pending before reassignment. History contains attempt/worker/timestamps/outcome/reason/mode/score/assignment_reason and successful duration. No public token fields.

Image limits: 1-20 files, JPG/JPEG/PNG extension and image/jpeg or image/png MIME, 1 byte–10 MiB each, <=4096/side and <=16 million pixels, no animation. Decoded content is verified. Any bad file rejects the batch and removes staged input. Multipart spooling precedes endpoint limits.

| Operation | params JSON | Output |
| --- | --- | --- |
| grayscale | `{}` | 8-bit grayscale PNG, same dimensions |
| resize | width/height integers 1-4096, product <=16 million | Exact dimensions; no automatic aspect preservation |
| gaussian_blur | odd kernel_size 1-99, default 5 | Same dimensions |
| edge_detection | threshold1/threshold2 integers 0-255, low<=high; defaults 100/200 | Grayscale Canny PNG |

Unknown operations/params rejected. Color decode discards alpha; EXIF orientation is not applied. Results require bounded valid PNG with expected dimensions and grayscale mode where required. Image structure is validated before final locked ownership commit; invalid bytes can return 422 before an ownership error. Dummy /complete cannot bypass image result validation.

## Codes and examples

200 read/update/poll/result; 201 registration/creation; 401 invalid modern session; 404 unknown entity or unavailable completed image; 409 duplicate online identity, offline/wrong owner/state/generation or changed completed result; 413 encoded byte limit; 415 MIME/extension; 422 JSON/form/parameter/image validation. Internal storage failures can return 500; inspect server logs/disk permissions. A retry response may already be assigned because distribution is atomic.

CMD, repository root, with actual local input:

```bat
curl.exe -i http://127.0.0.1:8000/health
curl.exe -i -X POST http://127.0.0.1:8000/images/tasks -F "files=@test_images\one.jpg;type=image/jpeg" -F "operation=grayscale"
curl.exe http://127.0.0.1:8000/tasks
```

Modern registration example:

```bat
curl.exe -i -X POST http://127.0.0.1:8000/workers/register -H "Content-Type: application/json" -H "X-Worker-Protocol: session-v1" -d "{\"worker_id\":\"manual-1\",\"hostname\":\"MY-PC\"}"
```

Retain the header locally, poll with it, then send returned assignment_token as X-Task-Assignment for start/finish/image transfers. Exact private-header exercises are in TESTING_GUIDE.md. There is no runtime scheduler-write endpoint.

## Dashboard transport

CORS_ALLOWED_ORIGINS defaults to http://127.0.0.1:5173,http://localhost:5173. Explicit comma-separated HTTP(S) origins only; no path, wildcard or credentials. HTTP CORS allows GET/POST and Content-Type without browser credentials. WebSocket Origin uses the same list; rejected origin closes 1008 before accept. Frames: `{"type":"snapshot","data":{"workers":[],"tasks":[],"scheduler":{...}}}`. No private token fields. Approximately two-second checks, changed snapshots only, five-second send deadline. Browser reconnect backoff is 1/2/4/8/16/30 seconds with five-second polling fallback. This is current state, not persistent event logging.
