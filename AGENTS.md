# Repository guidance

## Architecture and scope

- `master/`: Python FastAPI coordinator; future HTTP/WebSocket endpoints and a Python in-memory task queue.
- `worker/`: independent Python worker using requests, psutil and OpenCV.
- `frontend/`: future React + Vite + Tailwind dashboard.
- `tests/`: future unit and integration tests; `docs/`: design and experiment notes.
- `test_images/` and `outputs/`: local data and generated artifacts, excluded from Git.
- Do not introduce a database or machine learning without an explicit scope change.
- Phase 3 additionally permits JPG/PNG image uploads, HTTP input/result byte transfer, OpenCV grayscale/resize/Gaussian blur/edge detection and completed-result viewing/downloads. Preserve dummy tasks and static distribution. Do not implement adaptive scheduling, heartbeat, fault recovery or UI without further authorization.
- Validate upload types, byte/pixel limits and parameters. Store images only in ignored uploads/ and outputs/ using server-generated names. Never send master filesystem paths to workers. Image completion must validate ownership, running status and decoded output; it cannot bypass result upload through the dummy completion endpoint.
- Run one master process. Synchronize registry, queue, assignment and transition changes with the store lock. Registered idle workers are eligible; each may hold one active task. Preserve ownership checks and idempotent completion.
- Phase 4 permits psutil resource metrics, independent worker heartbeat threads, lifecycle-owned master timeout checks and session-fenced reconnection after offline detection. Preserve duplicate online registration protection. Legacy identities cannot reconnect. Do not introduce adaptive scheduling, task redelivery, retries or recovery (Phase 5).
- Keep session tokens private and out of worker-list responses/logs. Fence task updates and image transfers by the assignment's session generation; old tasks must not transfer to a new session. Use monotonic master receipt time for timeout decisions, server UTC for last_seen, and injected clocks in timeout tests.

## Conventions

- Keep master and worker dependencies and virtual environments separate.
- Use Python 3.13-compatible packages; update the relevant requirements file when adding a dependency.
- Prefer small functions, clear names, type hints for interfaces and explicit error handling.
- Use `snake_case` for Python modules/functions and `PascalCase` for classes. Future React components use `PascalCase`.
- Keep transport, scheduling and image-processing concerns separate as they are introduced.
- Document setup changes and interface decisions. Distinguish planned features from implemented behavior.
- Use headless OpenCV for workers unless a desktop GUI requirement is explicitly introduced.

## Safety

- Inspect existing files before changes; preserve user work and do not overwrite or delete unrelated files.
- Never commit secrets, `.env` files, virtual environments, uploaded datasets or generated output.
- Do not execute arbitrary commands or code received from workers or HTTP requests.
- When uploads are introduced, constrain file sizes/types and resolved paths to approved data directories.
- Keep future network services local by default; require explicit configuration before exposing them to other devices.
- Do not change machine-wide policies, install system services or modify firewall rules as part of routine setup.

## Incremental development and verification

- Implement one authorized development phase at a time; do not preemptively implement later phases.
- Prefer the smallest reviewable change and avoid unrelated refactors.
- Verify with the relevant virtual environment's Python executable.
- Run dependency checks after installation and focused tests when behavior is introduced.
- Report commands run, observed results, failures and remaining manual steps honestly; never claim unrun checks passed.
- Every future phase must include automated tests, execute the complete relevant regression suite (including earlier phases), fix introduced failures, and update `docs/TESTING_GUIDE.md`, `docs/AUTOMATED_TESTS.md` and `docs/TEST_RESULTS.md`. Record actual passed/failed counts and execution limitations; keep unperformed manual/LAN tests separate from automated results.

## Phase 5 scope update (supersedes earlier no-recovery restrictions)

- Permit selectable static/adaptive rule-based scheduling and bounded timeout/explicit-failure retries. Preserve static as the default baseline; no ML or performance claims.
- Require both current session and per-assignment generation for modern worker mutations and image transfers. Never expose credentials in public task history, logs or scheduler summaries. Legacy static clients cannot reconnect or receive secure retries.
- Keep assignment, recovery, queue deduplication, attempt history and result publication under the store lock. Retain original image inputs across retries. Completed results must not be replaced by stale attempts.
- Follow docs/phase5.md for scoring, fallback, fairness and attempt semantics. Master restart persistence, React frontend and Phase 6 are outside scope.

## Phase 6 scope update (supersedes earlier no-frontend restrictions)

- Permit the existing local React/Vite/TypeScript/Tailwind dashboard, read-only public snapshot WebSocket and explicit-origin CORS. Preserve all scheduling/recovery algorithms and earlier APIs.
- Never put worker session or assignment tokens in dashboard state, browser storage, public snapshots or URLs. Dashboard requests need no worker credentials. Worker-only originals remain restricted.
- Snapshot under the store lock, release it before encoding/network sends, bound update frequency and slow sends, and clean up disconnected clients. Frontend subscriptions must reconnect with backoff, provide bounded polling fallback and clean up on unmount.
- Frontend tests use Vitest/React Testing Library; run tests and production build along with full Python regressions. Record dependency advisories and blocked live/browser verification honestly. No benchmarking/Phase 7, database or new scheduling behavior.

## Phase 7 scope update

- Permit the standalone real-image HTTP benchmark client, seeded workloads, raw JSON/CSV and measured-data reports/SVGs. Do not modify startup-only scheduling through the benchmark client or bypass worker/session/assignment protection.
- Refuse contaminated topology/task setups, retain invalid/warmup/fault observations and require matched valid repeated trials before speedup/efficiency. Never publish mock test fixtures as experimental results or claim improvement without measurements.
- Keep generated datasets/results/reports/environment observations ignored. Preserve all phase regression commands and testing documents. No database, benchmarking UI, deployment framework or Phase 8.

## Phase 8 final handoff

- Permit final contract fixes, repository-relative Windows setup/start/verify/benchmark scripts and deployment/testing documentation. Preserve the in-memory architecture, credential boundaries and all regressions.
- Use scripts/test_all.cmd for complete verification; retain actual logs under ignored outputs/verification. Distinguish interrupted/failed runs from successful reruns and never mark manual/LAN/performance validation complete without evidence.
- Configuration is inert KEY=value data; terminal environment takes precedence. Never execute .env as shell code, overwrite user configuration, change system security/firewall policies or terminate unrelated processes.
- README is the current entry point; historical phase records can describe superseded behavior. Current API/architecture/LAN/checklist documents must match source. No additional phase, database, ML or orchestration features.
