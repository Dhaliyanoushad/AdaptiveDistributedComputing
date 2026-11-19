# Phase 7: reproducible performance evaluation

## Scope and execution

The benchmark is a separate CLI client under `benchmarks/`, using the worker Python environment (requests, Pillow, psutil). It uploads real image bytes through POST /images/tasks, observes existing GET /tasks, /workers and /scheduler responses, and downloads completed PNGs through the existing result endpoint. It never uses dummy timings as image measurements, changes scheduler configuration, acquires worker credentials, deletes tasks or terminates workers. Master/worker/dashboard algorithms and APIs are unchanged. No benchmarking dashboard section is added: standalone reports keep experiments independent of UI polling load.

Three modes:

- `single`: exactly one expected online worker; master must use static mode.
- `static`: at least two expected online workers; master must use static mode.
- `adaptive`: the same distributed worker set, with master started in adaptive mode.

Use separate isolated master restarts between modes. Run only the intended workers, with unique IDs. Worker enrollment must use current session-aware worker.py. The runner checks public online IDs and absence of unfinished unrelated tasks; it cannot inspect private sessions. Old legacy workers are not a valid experimental setup. Keep all inputs, parameters, environment metadata and non-mode scheduler settings identical. Do not run production uploads/dashboard traffic concurrently. Mode mismatch/topology/metadata failures before submission refuse the run rather than becoming a measured trial.

## Prepare reproducible workloads

From root in Windows CMD:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.workload --directory benchmarks\workloads\small-42 --profile small --seed 42
worker\.venv\Scripts\python.exe -m benchmarks.workload --directory benchmarks\workloads\medium-42 --profile medium --seed 42
worker\.venv\Scripts\python.exe -m benchmarks.workload --directory benchmarks\workloads\large-42 --profile large --seed 42
```

Defaults: small = 6×320×240, medium = 24×1280×720, large = 60×2560×1440. Override `--count`, `--width`, `--height`, `--format png|jpg`. The generator creates seeded RGB backgrounds and rectangles in Pillow. These are synthetic local inputs, not external photographs or a claimed representative photo dataset. Same seed, arguments and encoder versions produce matching bytes; SHA-256 manifests detect any differences. Existing directories are never overwritten. Maximum generated count 1000; API limits of 4096 per side, 16 million pixels and 10 MiB per encoded image apply.

Actual user datasets can be placed in another isolated directory. Files are sorted by name; content hashes/dimensions/count form the workload ID. The same files must be reused, not regenerated between modes. Generated manifest includes seed/profile/provenance. Keep external image origin/license/provenance in experiment metadata, and avoid committing private data. Generated workloads/results/reports and actual environment JSON are ignored; only source and environment.example.json are tracked.

Create local metadata by copying `benchmarks/environment.example.json` to `benchmarks/environment.json`, then edit **all** REPLACE placeholders. Use one identical metadata file across all modes, including hardware entries for both workers even in single mode. Record experiment ID, Git revision, master specs, each worker's physical-device identity/hostname/CPU/numeric RAM MiB/Python/OpenCV, power/background-load conditions and network configuration. The runner validates expected hardware entries and their hostname against registration. This is operator-supplied hardware metadata, not remotely measured hardware attestation. Client OS/Python/CPU-count/RAM are collected automatically.

Multiple worker processes on the same laptop share CPU, memory and usually the master process: this is a process-distribution experiment, not a two-physical-device comparison. Give those workers the same physical_device label. For LAN, record distinct devices and Wi-Fi/wired conditions. Do not pool these scenarios under the same experiment metadata.

## Run modes (startup-only scheduler)

Master terminal, repository root:

```bat
set "SCHEDULER_MODE=static"
master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 127.0.0.1 --port 8000
```

Worker terminal for the baseline (exactly one online worker):

```bat
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=bench-1"
worker\.venv\Scripts\python.exe worker\worker.py
```

Wait for heartbeats/metrics, then run:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.runner --master-url http://127.0.0.1:8000 --mode single --workers bench-1 --workload benchmarks\workloads\small-42 --operation grayscale --environment benchmarks\environment.json --warmups 1 --trials 3 --timeout 300 --output benchmarks\results
```

Stop/restart the master and workers explicitly before the distributed mode. Start master static and workers bench-1 and bench-2, then:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.runner --master-url http://127.0.0.1:8000 --mode static --workers bench-1,bench-2 --workload benchmarks\workloads\small-42 --operation grayscale --environment benchmarks\environment.json --warmups 1 --trials 3 --timeout 300 --output benchmarks\results
```

Stop/restart again with `set "SCHEDULER_MODE=adaptive"`, start the same two workers and run the same command with `--mode adaptive`. No runtime mode switch is attempted. Repeat the three-mode protocol for medium/large and each operation. For resize use `--operation resize --params "{\"width\":640,\"height\":480}"`; blur `--operation gaussian_blur --params "{\"kernel_size\":5}"`; edges `--operation edge_detection --params "{\"threshold1\":100,\"threshold2\":200}"`. Parameters follow existing backend limits. Each operation/parameter set is a separate comparison group.

Warmups default 1, measured trials default 3. Warmups execute the same pipeline and remain in raw output, but are excluded from statistics. History/OS caches remain across trials within a mode; separate restarts and identical warmup protocol reduce differences but do not eliminate cache/temperature/order effects. Rotate mode order in additional complete experiment blocks and retain experiment labels rather than claiming perfect experimental control. The runner exits on a failed trial; it does not silently proceed while old tasks may still run. Preserve that record and resolve isolation before explicitly retrying.

## Measurement boundaries and validity

Wall time uses client monotonic time. `started_at` is immediately before submission begins. `batch_elapsed_seconds` ends at the observation that all submitted tasks are terminal; it includes multipart upload time, queueing, HTTP transfer, image execution, retries and polling detection delay. Result validation/downloads are outside that batch interval and included in `client_total_seconds`. `batch_ended_at` and `ended_at` distinguish these UTC boundaries. Poll interval defaults 1 second; use the same interval for all modes and report it. Overhead is measurable and particularly significant for tiny workloads; results are application-level completion times, not pure CPU times.

- Throughput = successfully completed images / batch elapsed seconds. Partial runs retain observed completed throughput with invalid labels; no misleading speedup is generated.
- Initial queue time = first assignment UTC minus creation UTC, from the master.
- Assigned-to-start time = each attempt's start minus assignment timestamp.
- Retry queue time = next assignment minus previous attempt finish when available.
- Execution-and-transfer time = existing server monotonic `duration_seconds`, measured start-to-accepted-completion. This includes image download, OpenCV processing, result upload and master validation. **Worker-only OpenCV time is not separately instrumented** and remains unavailable, never inferred from dummy delays.
- Task end-to-end latency = master completed_at minus created_at (successful tasks only). Server-local timestamps avoid cross-device subtraction. Negative/missing times become null.
- Retry counts: tasks with attempt_count>1; retry attempts = sum(attempt_count−1). History retains timeout/failure/reassignment reasons.
- CPU/RAM samples are whole-host, last-reported worker metrics with last_seen and client observation time. Repeated values can represent the same heartbeat, not additional independent samples. Master reads and observations add overhead. High-frequency worker-only resource peaks may be missed.
- Allocated/participating worker count is the exact intended online pool; executing_worker_ids separately lists workers appearing in attempt history. A policy may leave some pool members unused. Efficiency uses the allocated count, not a post-hoc smaller denominator.

Every upload response must return exactly one unique new ID per image. Run UUID maps each task to its input filename/hash. Inputs are rehashed before submission. The runner verifies no unrelated new tasks, no disappeared previous tasks/master reset, unchanged scheduler configuration, expected online worker set and stable hostnames. It checks every output's PNG format/dimensions/grayscale mode and records output hashes; existing worker/assignment fencing remains authoritative. A failure after an uncertain POST may leave uncorrelated server tasks; the report says so. Inspect GET /tasks before a new experiment.

Clean-comparison validity requires all expected tasks completed, all outputs validated, positive finite duration, no retry and no detected isolation/topology change. Fault trials are retained but excluded from speedup. Reconnected same-host sessions with no observed offline interval cannot be fully detected through public APIs; retries/history expose task-level effects, and operator isolation remains necessary. Output structure/hash recording is not cryptographic proof of correct processing by an untrusted worker.

## Reporting

```bat
worker\.venv\Scripts\python.exe -m benchmarks.report --source benchmarks\results --output benchmarks\reports\experiment-01
```

Choose a new report directory. Outputs:

- `benchmarks/results/<run UUID>/run.json`: configuration, hardware metadata, workload manifest, correlated tasks, raw snapshots/resource samples, result hashes, metrics, issues and UTC/elapsed boundaries.
- Report `trials.csv`, `tasks.csv`, `resources.csv`, `summary.json`, `report.md`.
- Standalone SVGs: `elapsed.svg`, `throughput.svg`, `speedup.svg`, `efficiency.svg`, `distribution.svg`, `resources.svg`. Open in a browser or embed/export them for the project report. They use actual saved observations only. No observations yields an explicit empty graph.

Grouping requires identical workload hashes/operation/parameters/environment and non-mode scheduler settings. Static/adaptive must have the same sorted worker IDs; the single worker must be included in the distributed pool. At least three valid measured trials per group and exactly one baseline are required. Any invalid measured trial prevents speedup/efficiency for that group instead of silently removing it. Individual failed/warmup trials remain in exports. Statistics use valid measured trials: mean, median and sample standard deviation (SD is null for fewer than two samples).

`speedup = mean(single batch elapsed) / mean(distributed batch elapsed)`; `efficiency = speedup / allocated worker count`. These are ratios of means, not means of per-trial ratios. N/A does not mean zero. A speedup below 1 means slower in those recorded conditions; do not generalize to all devices or claim adaptive superiority from unmeasured runs. Multiple experiment labels or hardware/network conditions remain distinct groups.

## Cancellation and open issues

Ctrl+C during a trial records cancelled/invalid state and leaves server tasks untouched. Deadline checks plus bounded HTTP connect/read timeouts stop observation; an in-flight request/DNS/OS stall may exceed the nominal deadline, so this is not a hard real-time guarantee. Timed-out/invalid trials retain evidence; do not delete tasks or kill production workers. Master restart persistence remains unsupported. No benchmark is auto-started at application startup.

No actual performance benchmark has been executed during implementation. All generated test records live in temporary test directories and are explicitly fixtures. Existing WinError 10013 prevented earlier live localhost/browser verification; it is not marked fixed. npm audit was rechecked and still reports 1 moderate/2 critical development findings; another compatible-version installation attempt failed DNS ENOTFOUND. No unsafe forced upgrade was used. Live HTTP, LAN and hardware performance trials remain pending.
