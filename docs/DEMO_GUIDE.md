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
