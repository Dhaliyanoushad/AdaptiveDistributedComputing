# Repository guidance

## Architecture and scope

- `master/`: Python FastAPI coordinator; future HTTP/WebSocket endpoints and a Python in-memory task queue.
- `worker/`: independent Python worker using requests, psutil and OpenCV.
- `frontend/`: future React + Vite + Tailwind dashboard.
- `tests/`: future unit and integration tests; `docs/`: design and experiment notes.
- `test_images/` and `outputs/`: local data and generated artifacts, excluded from Git.
- Do not introduce a database or machine learning without an explicit scope change.
- Phase 2 permits HTTP health checks, worker registration/listing, an in-memory dummy-task registry/FIFO queue, static round-robin distribution and worker polling/start/completion/failure updates. Do not implement image processing, adaptive scheduling, heartbeat, fault recovery or UI without further authorization.
- Run one master process. Synchronize registry, queue, assignment and transition changes with the store lock. Registered idle workers are eligible; each may hold one active task. Preserve ownership checks and idempotent completion.
- Worker reconnection, task redelivery and retries are not supported yet. Keep duplicate registration protection.

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
