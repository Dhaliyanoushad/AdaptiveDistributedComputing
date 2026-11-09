# Phase 2: task queue and static distribution

Phase 1 health, registration and worker listing remain available. The registration endpoint now documents HTTP 409 in OpenAPI/Swagger. Duplicate registration is still rejected: reconnecting a worker with the same ID is not supported.

## API and data

| Request | Successful response |
| --- | --- |
| `POST /tasks` | 201, array of created tasks |
| `GET /tasks` | 200, all tasks in submission order |
| `GET /tasks/{task_id}` | 200, one task; 404 for an unknown ID |
| `POST /workers/{worker_id}/next-task` | 200, `{"task": <task>}` or `{"task": null}`; 404 for an unregistered worker |
| `POST /tasks/{task_id}/start` | 200, running task |
| `POST /tasks/{task_id}/complete` | 200, completed task |
| `POST /tasks/{task_id}/fail` | 200, failed task |

Submit an object containing 1-1000 tasks:

```json
{
  "tasks": [
    {"operation": "dummy", "payload": {"label": "first"}},
    {"operation": "dummy", "payload": {"label": "second"}},
    {"operation": "dummy", "payload": {"fail": true}}
  ]
}
```

Only operation `dummy` is accepted. Payload is a JSON object and defaults to `{}`. Arbitrary commands/code are never executed. `payload.fail: true` simulates a task failure after the configured delay; other payload values are retained without processing. Invalid batches return 422 and create no tasks.

Each task has a UUID `task_id`, `operation`, `payload`, `status`, `assigned_worker`, `attempt_count`, `created_at`, `updated_at`, `assigned_at`, `started_at`, `completed_at`, `failed_at` and optional `error`. Timestamps are UTC. Lifecycle-specific timestamps begin as null. Attempt count starts at 0 and increments to 1 on assignment; there are no retries in this phase.

## States, ownership and synchronization

```text
pending -> assigned -> running -> completed
                              -> failed
```

The FIFO pending queue is a Python deque. On submission, worker registration or task completion/failure, the master assigns queued tasks using a rotating cursor through worker registration order. Eligible means registered with no assigned/running task. Busy workers are skipped. Each worker holds at most one active task. Assignment happens before polling; submission can therefore return tasks already in `assigned` state.

Polling delivers that worker's assigned task only once. Concurrent/repeated polls cannot deliver it twice or transfer it to another worker. Subsequent polls return `{"task": null}` while the assignment is already delivered or running. The worker then sends `start`, waits `TASK_DELAY`, and sends `complete` or `fail`. Completion/failure releases the worker for another pending task.

Round-robin applies to workers eligible at each assignment. Faster workers can receive more tasks because busy workers are skipped; this is a static rule with no load measurement or adaptive scheduling.

Start/completion bodies are `{"worker_id":"local-worker-1"}`. Failure also requires a nonempty `error` string of at most 500 characters. Unknown tasks/workers return 404. Wrong owners and invalid transitions return 409. Start requires a previously polled assignment. Finishing requires a running task. Failed and completed tasks are terminal. A repeated completion by the original owner returns the same completed record with unchanged timestamps/attempt count and does not affect its next task. Repeated starts/failures return 409.

A process-local reentrant lock protects registration, the queue, cursor, task mutations, delivery tracking and response snapshots. Run **one** Uvicorn process without reload. Multiple master processes do not share this lock or state. There is no authentication yet: worker IDs identify ownership but are not credentials.

## Start locally (Windows CMD)

Terminal 1:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=local-worker-1"
set "POLL_INTERVAL=1"
set "TASK_DELAY=3"
worker\.venv\Scripts\python.exe worker\worker.py
```

Terminal 3:

```bat
cd /d C:\Users\daliy\Desktop\AdaptiveDistributedComputing
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=local-worker-2"
set "POLL_INTERVAL=1"
set "TASK_DELAY=3"
worker\.venv\Scripts\python.exe worker\worker.py
```

`POLL_INTERVAL` must be finite and greater than zero; `TASK_DELAY` must be finite and nonnegative. Both are seconds. HTTP calls retain connection/read timeouts and do not retry. Workers poll when idle and remain running after each task. Registration conflicts, network errors and rejected updates stop the worker with exit 1. Ctrl+C exits 0. No new dependencies are needed.

## Manual verification

Use a fourth CMD terminal (or Swagger at `http://127.0.0.1:8000/docs`).

1. Check `/health` and `/workers`. Wait until both worker IDs appear, then submit six tasks:

   ```bat
   curl.exe -i -X POST http://127.0.0.1:8000/tasks -H "Content-Type: application/json" -d "{\"tasks\":[{\"operation\":\"dummy\"},{\"operation\":\"dummy\"},{\"operation\":\"dummy\"},{\"operation\":\"dummy\"},{\"operation\":\"dummy\"},{\"operation\":\"dummy\",\"payload\":{\"fail\":true}}]}"
   curl.exe http://127.0.0.1:8000/tasks
   ```

   On a fresh master with both workers idle, the first two tasks are assigned to the workers in registration order; the rest remain pending until a worker finishes. Repeatedly inspect `/tasks` to see `running` and terminal states. Expect five completed tasks, one simulated failure, and one attempt per task. Worker terminals print task IDs and transitions. Completion order and later assignments can vary with polling timing.

2. Copy a task ID and its assigned worker from the response. Substitute them below:

   ```bat
   set "TASK_ID=PASTE_TASK_ID_HERE"
   set "OWNER=local-worker-1"
   curl.exe http://127.0.0.1:8000/tasks/%TASK_ID%
   curl.exe -i -X POST http://127.0.0.1:8000/tasks/%TASK_ID%/complete -H "Content-Type: application/json" -d "{\"worker_id\":\"%OWNER%\"}"
   ```

   Choose a **completed** task for the repeated-completion check: expect 200 and unchanged task data. Starting that completed task returns 409. Completing it as the other registered worker also returns 409. GET with an unknown task ID returns 404. Submitting an unsupported operation returns 422.

3. To observe pending tasks directly, use a fresh master **without workers**, submit a batch, and inspect `/tasks`: all are pending, unassigned, with attempt count 0. Launch a worker and see one task assigned, polled and executed; later tasks are dispatched as it finishes.

4. To inspect claiming/transitions manually without a running worker consuming the assignment, use a fresh master and Swagger. Register `manual-a` and `manual-b`, submit one task, and note its owner. Poll the owner's `/next-task`: it returns that task. Poll again: `task` is null. Poll the other worker: also null. Starting before polling or completing before starting returns 409. Use the owner's ID to start, then complete; repeat completion and confirm unchanged timestamps. The automated tests also issue concurrent polls and thread-level completion requests.

5. Launch another worker process using an already registered ID: expect HTTP 409 and exit 1. Swagger's registration responses now include 409. Reconnection is deliberately unsupported.

## Limits and verification

All data is in memory and resets on master restart. Workers are not removed when they stop. A disconnected worker remains registered, and its assigned/running task can remain stuck. A lost poll response is not redelivered. Stopping a worker during a task does not fail/requeue it. A completion response lost after acceptance is not retried automatically, although repeating it manually is safe. These limits require future recovery work, which is outside this phase.

Verification performed in the existing Python environments:

- Master: `master\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_master*.py" -v` ran **24 tests**, all passed. This includes all 10 Phase 1 tests, task validation, state transitions, round-robin assignment, simultaneous polls, thread-level delivery checks, duplicate completion, registry isolation and the documented registration conflict.
- Worker: `worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -v` ran **11 tests**, all passed. The 5 Phase 1 registration tests remain, with the polling loop mocked to isolate registration. New tests cover polling/execution, simulated failure, rejected starts, timing configuration, communication failure and clean Ctrl+C handling.
- Each environment's `python -m pip check` returned 0 with `No broken requirements found.` Runtime requirements were not changed.
- A real localhost integration check started one master on port 8012 and two distinct worker processes. Six submitted tasks produced five completions and one simulated failure, all with attempt count 1. Both workers received work. The initial response assigned the first task to worker A, the second to worker B and left four pending. Later assignment order reflected which workers were idle. All three temporary processes were cleaned up.
- `git diff --check` found no whitespace errors in tracked changes. Git emitted normal Windows LF/CRLF conversion warnings.

No image processing, adaptive scheduling, heartbeat monitoring, fault recovery, database, machine learning or frontend is implemented. No real two-laptop test was performed.
