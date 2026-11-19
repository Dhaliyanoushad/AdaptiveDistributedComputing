"""HTTP API for registration and Phase 2 dummy-task distribution."""

import logging
import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request, Response, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from master.models import Task, TaskBatch, TaskFailure, TaskPoll, TaskUpdate, WorkerRegistration
from master.task_store import StoreError, TaskStore
from master.image_routes import image_router
from master.models import Heartbeat, WorkerRecord
from master.monitoring import positive_setting, timeout_loop
from master.scheduling import SchedulerSettings
from master.dashboard import dashboard_origins, dashboard_router

logger = logging.getLogger("uvicorn.error")


def create_app(*, input_dir: Path | None = None, output_dir: Path | None = None, store_override=None) -> FastAPI:
    """Create an application with an independent, nonpersistent registry."""
    store = store_override or TaskStore(timeout=positive_setting("WORKER_TIMEOUT", 10), settings=SchedulerSettings.from_environment())
    check_interval = positive_setting("TIMEOUT_CHECK_INTERVAL", 1)

    @asynccontextmanager
    async def lifespan(application):
        sweeper = asyncio.create_task(timeout_loop(store, check_interval))
        application.state.timeout_task = sweeper
        try:
            yield
        finally:
            sweeper.cancel()
            with suppress(asyncio.CancelledError):
                await sweeper

    application = FastAPI(title="Adaptive Distributed Computing - Phase 6", lifespan=lifespan)
    origins = dashboard_origins()
    application.add_middleware(CORSMiddleware, allow_origins=origins,
        allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['Content-Type'])
    application.include_router(dashboard_router(store,origins))
    application.state.store = store
    application.state.workers = store.workers
    root = Path(__file__).resolve().parents[1]
    application.include_router(image_router(store, input_dir or root / "uploads", output_dir or root / "outputs"))

    @application.exception_handler(StoreError)
    async def store_error_handler(request: Request, exc: StoreError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/workers/register", status_code=201,
                      responses={409: {"description": "Worker is online or legacy identity cannot reconnect"},
                                 201: {"headers": {"X-Worker-Session": {"schema": {"type": "string"}, "description": "Private session token for session-v1 registrations"}}}})
    async def register_worker(worker: WorkerRegistration, response: Response,
                              x_worker_protocol: str | None = Header(default=None)) -> WorkerRegistration:
        aware = x_worker_protocol == "session-v1"
        registered = store.register(worker, session_aware=aware)
        if aware:
            response.headers["X-Worker-Session"] = store.session_token(worker.worker_id)
        logger.info("Worker registered: worker_id=%r hostname=%r", worker.worker_id, worker.hostname)
        return registered

    @application.get("/workers")
    async def list_workers() -> list[WorkerRecord]:
        return store.list_workers()

    @application.get("/workers/{worker_id:path}", responses={404: {"description": "Unknown worker"}})
    async def get_worker(worker_id: str) -> WorkerRecord:
        return store.get_worker(worker_id)

    @application.post("/workers/heartbeat", responses={401: {"description": "Invalid session"},
                      404: {"description": "Unknown worker"}, 409: {"description": "Offline worker must register again"}})
    async def heartbeat(update: Heartbeat, x_worker_session: str | None = Header(default=None)) -> WorkerRecord:
        return store.heartbeat(update, x_worker_session)

    @application.post("/tasks", status_code=201)
    async def submit_tasks(batch: TaskBatch) -> list[Task]:
        return store.submit(batch.tasks)

    @application.get("/tasks")
    async def list_tasks() -> list[Task]:
        return store.list_tasks()

    @application.get('/scheduler')
    async def scheduler_info() -> dict:
        return store.scheduler_info()

    @application.get('/tasks/{task_id}/attempts')
    async def task_attempts(task_id: str) -> list[dict]:
        return store.get_task(task_id).attempt_history

    @application.get("/tasks/{task_id}", responses={404: {"description": "Task not found"}})
    async def get_task(task_id: str) -> Task:
        return store.get_task(task_id)

    @application.post("/workers/{worker_id:path}/next-task",
                      responses={401: {"description": "Missing or stale worker session"},
                                 409: {"description": "Worker offline or task belongs to an old session"},
                                 404: {"description": "Worker not registered"}})
    async def next_task(worker_id: str, x_worker_session: str | None = Header(default=None)) -> TaskPoll:
        task, assignment = store.poll_assignment(worker_id, x_worker_session)
        return TaskPoll(task=task, assignment_token=assignment)

    errors = {401: {"description": "Invalid session"}, 404: {"description": "Task or worker not found"},
              409: {"description": "Wrong owner or invalid task-state transition"}}

    @application.post("/tasks/{task_id}/start", responses=errors)
    async def start_task(task_id: str, update: TaskUpdate, x_worker_session: str | None = Header(default=None),
                         x_task_assignment: str | None = Header(default=None)) -> Task:
        return store.update(task_id, update.worker_id, "start", token=x_worker_session, assignment=x_task_assignment)

    @application.post("/tasks/{task_id}/complete", responses=errors)
    async def complete_task(task_id: str, update: TaskUpdate, x_worker_session: str | None = Header(default=None),
                            x_task_assignment: str | None = Header(default=None)) -> Task:
        return store.update(task_id, update.worker_id, "complete", token=x_worker_session, assignment=x_task_assignment)

    @application.post("/tasks/{task_id}/fail", responses=errors)
    async def fail_task(task_id: str, update: TaskFailure, x_worker_session: str | None = Header(default=None),
                        x_task_assignment: str | None = Header(default=None)) -> Task:
        return store.update(task_id, update.worker_id, "fail", update.error, token=x_worker_session,
                            assignment=x_task_assignment, retryable=update.retryable)

    return application


app = create_app()
