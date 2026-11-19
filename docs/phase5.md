# Phase 5: adaptive scheduling and fault recovery

This phase adds a selectable rule-based policy and bounded retries. No performance improvement is claimed; benchmark comparisons remain future work. No UI, database, ML, message broker or deployment framework was added.

## Configuration and policy

Set variables in the master CMD before startup. Values are validated; invalid mode, nonfinite numbers, negative weights, invalid ranges or all-zero weights fail startup.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SCHEDULER_MODE` | `static` | `static` or `adaptive` |
| `MAX_TASK_ATTEMPTS` | `3` | Total assignments, including initial assignment; integer 1-100 |
| `METRICS_MAX_AGE` | `8` | Maximum metric age in seconds, >0 |
| `FAIRNESS_MAX_SKIPS` | `5` | Eligible assignment decisions a worker may lose before forced selection, integer >=1 |
| `HISTORY_MIN_SAMPLES` | `3` | Successful samples before using performance history, integer >=1 |
| `MIN_AVAILABLE_RAM_MB` | `128` | Minimum fresh available RAM for adaptive eligibility, >=0 |
| `RAM_TARGET_MB` | `1024` | Saturation point for available-memory score, >0 |
| `SCHEDULER_CPU_WEIGHT` | `.35` | CPU headroom weight |
| `SCHEDULER_RAM_WEIGHT` | `.20` | RAM headroom weight |
| `SCHEDULER_AVAILABLE_WEIGHT` | `.15` | Available RAM weight |
| `SCHEDULER_LOAD_WEIGHT` | `.15` | Assigned/running count weight |
| `SCHEDULER_HISTORY_WEIGHT` | `.15` | Observed completion-time weight |

Weights are nonnegative finite numbers and at least one must be positive. All Phase 4 heartbeat/timeout variables remain unchanged (WORKER_TIMEOUT=10, TIMEOUT_CHECK_INTERVAL=1, HEARTBEAT_INTERVAL=3, HEARTBEAT_HTTP_TIMEOUT=2). Workers retain MASTER_URL (loopback default), WORKER_ID (hostname), POLL_INTERVAL=1 and TASK_DELAY=.5. Task HTTP timeouts remain connect 3.05/read 10 seconds. No new dependencies are required.

Static mode retains registration-order round-robin and skips offline/busy workers. Adaptive mode requires an online, idle, session-aware worker. Heartbeats use server monotonic receipt time for freshness. A full fresh sample requires all three resource fields non-null. With any full fresh samples present, only those meeting the minimum available-RAM threshold are candidates; if all fail the threshold, tasks wait. Missing/stale samples are never compared against fresh scores. If no idle session-aware worker has a full fresh sample, use conservative round-robin fallback among those idle online session-aware workers. This fallback cannot guarantee free RAM; its decision is explicitly recorded. Legacy identities are excluded from adaptive mode.

For eligible workers, maximize this normalized weighted score:

```text
score = (wc*(1-CPU/100) + wr*(1-RAM/100)
         + wa*min(available_MiB/RAM_TARGET_MB,1)
         + wl/(1+active_tasks) + wh*performance) / (wc+wr+wa+wl+wh)
performance = 0.5 before HISTORY_MIN_SAMPLES successful completions
performance = 1/(1+mean_completion_seconds) thereafter
```

The mean uses at most the last 100 successful durations from start to accepted completion. It includes transfer time and mixes operations; it is not a hardware benchmark. With one active task maximum, load primarily acts through eligibility; all selectable workers currently have load 0. Score ties use the rotating round-robin order. No random choices are made.

Each eligible worker skipped by a decision gains a fairness count. At the configured threshold, an overdue eligible worker is selected in rotating order before score selection. Selected workers reset their counter. Workers must remain eligible to receive this guarantee; offline, busy or unavailable-metric workers are not promised assignments until eligible. Resources only affect future assignments, never running-task migration. Mode is read at master creation; there is no live configuration-write API.

## Sessions, attempts and retry policy

Updated workers register with `X-Worker-Protocol: session-v1` and receive private `X-Worker-Session`. The polling response now contains `task` plus private `assignment_token` (null when no task). Send that value as `X-Task-Assignment` on task start/complete/fail, image input download and result upload, together with the worker session header. Updated worker.py does this automatically. Public task/history/scheduler responses never include assignment tokens or session secrets.

Legacy static clients keep their original first-assignment behavior. They cannot reconnect, use adaptive mode or receive secure retries. An unfinished legacy task becomes terminal failed on timeout. A retried task is never downgraded to a legacy worker. Existing session-v1 clients from Phase 4 must update to send assignment tokens; absent/stale tokens now return 409. Unknown worker/task remains 404; invalid session 401; invalid state/owner/generation 409; invalid payload 422. No-token legacy enrollment remains trusted-network compatibility, not authenticated identity.

Attempts increment on **assignment**, not polling or start. Polling, duplicate completion and duplicate recovery do not increment the count. Timeout recovery runs in the existing master lifecycle sweep and under the shared store lock:

```text
assigned/running -> heartbeat timeout -> pending -> assigned (new token)
running -> reported retryable failure -> pending -> assigned (new token)
assigned/running -> exhausted attempt budget -> failed
running -> permanent processing failure -> failed
```

Successful completion is terminal and idempotent for the current owner/session/generation. Invalid duplicate starts/failures are rejected; an old failure report cannot fail a newer attempt. Every recovery invalidates the previous effective ownership via state/session checks and the next assignment rotates the attempt token. Offline workers cannot revive via heartbeat; they must explicitly register again. Reconnection grants no previous assignment token. It may receive a genuinely new attempt with incremented count, even for the same task ID.

Explicit `/fail` accepts strict boolean `retryable` (default false). Input/parameter/decode validation errors are permanent by default. Worker image transport/OS errors report retryable=true when the master is reachable. Dummy `{ "fail": true, "retryable": true }` supports deterministic retry-limit testing. Poll/start/completion network failures stop the worker; its heartbeat sender then stops and the master recovers after timeout. There is no blind client retry of mutations. If the master already accepted a completion but its response was lost, completed work stays completed and is not recovered again. Heartbeat send failures alone do not stop task processing; later heartbeat attempts remain scheduled.

Each task has `attempt_history`: attempt number, worker, assignment/start/finish timestamps, mode, score, assignment_reason, outcome and retry/failure reason. Completed attempts also record observed duration. Current task fields represent the latest attempt; history preserves earlier attempts. The original input UUID file remains available for each image retry. No workers online means tasks stay pending with one queue entry each. Retries append at the FIFO tail; a retry-only pending head can wait for a modern worker even if legacy workers are idle.

## Output and shutdown integrity

The existing decoded-output checks (format, dimensions, grayscale mode and limits) remain. Ownership/session/generation/state validation and exclusive UUID output creation occur under the store lock; only a complete validated file is published as completed. A failed commit removes its new file. Identical repeat result bytes are accepted for the current completed attempt; different bytes or stale attempts cannot replace a completed output. Structural validation does not prove an untrusted worker ran the algorithm.

Master lifespan shutdown cancels the periodic recovery loop; worker shutdown signals its heartbeat thread. All registry, history, session and queue state is in memory and is lost on master restart; disk inputs/outputs remain but are not rediscovered or resumed. Restart workers explicitly after master restart. Exactly-once physical computation is not claimed: an offline worker may still compute while a new attempt runs, but only a currently valid attempt can publish a result.

## Read APIs

- `GET /scheduler`: selected configuration, pending count, per-worker active load, fairness skip count, successful sample count and mean observed seconds.
- `GET /tasks` and `GET /tasks/{task_id}`: current task plus attempt_history.
- `GET /tasks/{task_id}/attempts`: attempt history alone; unknown ID returns 404.
- Existing health/registration/worker/task/image endpoints remain. Task/image mutation headers appear in Swagger.

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for CMD/manual/LAN procedures, [AUTOMATED_TESTS.md](AUTOMATED_TESTS.md) for coverage and [TEST_RESULTS.md](TEST_RESULTS.md) for observed runs. Manual and LAN checks are not yet executed.
