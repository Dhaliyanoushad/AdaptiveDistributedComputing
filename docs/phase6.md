# Phase 6: local React dashboard

The dashboard uses React + Vite + TypeScript, Tailwind 3/PostCSS, Fetch and a read-only WebSocket. No routing/charting library was needed: six accessible navigation sections share one state subscription, and CPU/RAM values use labeled progress meters. No database, benchmarking or scheduling/recovery changes were made.

Sections: Overview (actual counts/status/activity), Image processing (multipart batches and parameters), Workers (status/resources/last heartbeat), Tasks (search/filter/current owner/attempt history), Results (completed PNG preview/download) and Scheduling (read-only policy/config/load/stored retry events).

Configuration: VITE_MASTER_URL defaults to http://127.0.0.1:8000; CORS_ALLOWED_ORIGINS defaults to http://127.0.0.1:5173,http://localhost:5173. Both HTTP(S) base URL and explicit origins are validated. Vite variables are embedded into the frontend and must never contain secrets. Use only trusted-network deployment: this dashboard does not introduce authentication to the existing prototype.

Existing GET workers/tasks/scheduler and task-attempt endpoints provide state. Existing POST images/tasks provides batch submission. Existing completed-result endpoints provide previews/downloads. Originals remain worker-only; the UI explains their absence rather than bypassing ownership. No session/assignment credentials are requested, stored or sent by the dashboard.

WS /ws/dashboard validates the browser Origin, accepts no mutations and sends a public snapshot initially and when state changes (roughly two-second checks). Snapshots are copied under the store lock; JSON encoding and bounded network sends happen outside it. Slow/disconnected clients are dropped. No worker tokens or assignment tokens are serialized. History is the existing stored attempt history, not a newly invented timeout event log.

The client has one subscription, refreshes after connection recovery, retries sockets with bounded exponential backoff and falls back to one nonoverlapping public refresh every five seconds when disconnected. Old socket messages are ignored. Initial loading, no data, stale snapshots, unavailable metrics and errors are distinct states. Upload status is validation/submitting/success/error rather than an invented byte-progress percentage; returned tasks are not assumed completed. Backend validation remains authoritative.

Installation, CMD startup and unexecuted teammate scenarios: TESTING_GUIDE.md section 10. Actual automated results/blocked verification: TEST_RESULTS.md. Dependency audit advisories remain unresolved pending npm registry access. No real-browser or two-laptop acceptance test is claimed.
