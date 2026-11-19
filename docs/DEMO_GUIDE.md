# Proposed 10–15 minute project demonstration

**Procedure only; not executed/validated as a live demo.** Rehearse with the teammate after installation and manual checks. Choose nonprivate images, prepare an empty isolated master and two unique workers, then use startup scripts from README/TWO_LAPTOP_SETUP. Do not improvise a public deployment or show private tokens.

| Time | Action | Expected evidence |
| --- | --- | --- |
| 0–2 min | Explain actual architecture, one master and two workers; show /health, Swagger and dashboard | Health 200, real zero/initial counts, no fabricated statistics |
| 2–4 min | Start two workers; show Workers cards and /workers | Hostnames, online status, changing last_seen, CPU/RAM/MiB; no credential fields |
| 4–7 min | Upload two images, choose grayscale/resize, track task IDs | Pending/assigned/running/completed, one task per image, valid output preview/download |
| 7–9 min | Open task details/scheduling | Static or adaptive startup mode, actual assignment history/reasons, read-only mode display |
| 9–12 min | Demonstrate worker interruption/recovery | Stop actual owning worker, wait timeout, show attempt/reassignment and unchanged accepted output protection |
| 12–15 min | Explain benchmark workflow and limitations; show only real recorded reports if available | Seed/manifest, isolated modes, repeated trials/invalid handling; no speedup claim without measurements |

Use TASK_DELAY=15 dummy work to make interruption observable if real images complete too quickly. Label it as a recovery demonstration, never image benchmark timing. A tiny image completing before interruption is not a failure-recovery pass. Do not force an unsafe CPU load or delete evidence to make the demo look cleaner.

To compare modes, stop/reset processes and restart with SCHEDULER_MODE=adaptive; do not imply a runtime toggle exists. Time may not permit a complete three-mode benchmark during the live demo; demonstrate preparation/commands and describe methodology rather than generating fictional graphs. Current implementation has no actual performance experiment evidence.

Have fallback evidence ready only after real tests exist: reviewed screenshots, actual run IDs, result PNGs and recorded defects. If live networking is blocked, state the limitation and show automated ASGI/processor test evidence explicitly as automated tests, not LAN execution. Known WinError 10013 and development-tool audit findings must not be concealed.

Finish by stopping owned workers/frontend/master, clearing private test token variables and identifying remaining manual acceptance work. Master restart resets metadata; output files alone do not restore tasks.

## Phase 9 presentation wording and preservation

Procedure only — NOT YET EXECUTED. Keep the same demo sequence above, using Dashboard and Process Images for the former Overview/Image processing destinations. Use CODE_WALKTHROUGH.md for source explanations and FEATURE_CHECKLIST.md when answering which tests preserve a feature.

1. Show real Dashboard counts and connection state, then Process Images: select files, describe the chosen operation, submit and follow Task IDs. Explain that accepted does not mean completed.
2. In Workers, point out hostname, CPU, RAM, Available RAM (MiB), Active Tasks and Last Heartbeat. Do not treat stale values as current utilization or missing values as zero.
3. In Tasks, use search/status filters and open details. Explain pending/assigned/running/completed/failed and show actual reasons/attempts. A retry request does not establish successful reassignment or completion.
4. In Scheduling, identify Static Scheduling or Adaptive Scheduling and expand Technical details if needed (initially visible). Explain that SCHEDULER_MODE is set at Master startup. No live mode toggle is supported.
5. Use Benchmark reports guidance to explain Throughput, Speedup and Efficiency, then show only genuinely recorded CSV/JSON/Markdown/SVG reports. Reports remain external files; this page does not load experimental results. Adaptive Scheduling may be slower for some workloads.

Exact existing CMD entry points (separate terminals, from repository): scripts\start_master.cmd; set "WORKER_ID=worker-1" then scripts\start_worker.cmd; a second terminal with worker-2; scripts\start_frontend.cmd. For actual copyable multiline commands and expected results use TESTING_GUIDE.md Phase 9. Run scripts\test_all.cmd to obtain automated evidence before rehearsal. Current 185-test pass is automated evidence, not a live demo/LAN/browser pass.

Before presentation, teammate must execute P9-01–12 plus earlier cases, including responsive and keyboard checks; record actual outcomes and screenshots. WinError 10013, npm advisories, clean-machine/LAN/browser/performance validation and in-memory restart loss remain disclosed.
