"""HTTP API for registration and Phase 2 dummy-task distribution."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from master.models import Task, TaskBatch, TaskFailure, TaskPoll, TaskUpdate, WorkerRegistration
from master.task_store import StoreError, TaskStore

logger = logging.getLogger("uvicorn.error")


def create_app() -> FastAPI:
    """Create an application with an independent, nonpersistent registry."""
    application = FastAPI(title="Adaptive Distributed Computing - Phase 2")
    store = TaskStore()
    application.state.store = store
    application.state.workers = store.workers

    @application.exception_handler(StoreError)
    async def store_error_handler(request: Request, exc: StoreError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/workers/register", status_code=201,
                      responses={409: {"description": "Worker ID already registered; reconnection is not supported"}})
    async def register_worker(worker: WorkerRegistration) -> WorkerRegistration:
        registered = store.register(worker)
        logger.info("Worker registered: worker_id=%r hostname=%r", worker.worker_id, worker.hostname)
        return registered

    @application.get("/workers")
    async def list_workers() -> list[WorkerRegistration]:
        return store.list_workers()

    @application.post("/tasks", status_code=201)
    async def submit_tasks(batch: TaskBatch) -> list[Task]:
        return store.submit(batch.tasks)

    @application.get("/tasks")
    async def list_tasks() -> list[Task]:
        return store.list_tasks()

    @application.get("/tasks/{task_id}", responses={404: {"description": "Task not found"}})
    async def get_task(task_id: str) -> Task:
        return store.get_task(task_id)

    @application.post("/workers/{worker_id}/next-task",
                      responses={404: {"description": "Worker not registered"}})
    async def next_task(worker_id: str) -> TaskPoll:
        return TaskPoll(task=store.poll(worker_id))

    errors = {404: {"description": "Task or worker not found"},
              409: {"description": "Wrong owner or invalid task-state transition"}}

    @application.post("/tasks/{task_id}/start", responses=errors)
    async def start_task(task_id: str, update: TaskUpdate) -> Task:
        return store.update(task_id, update.worker_id, "start")

    @application.post("/tasks/{task_id}/complete", responses=errors)
    async def complete_task(task_id: str, update: TaskUpdate) -> Task:
        return store.update(task_id, update.worker_id, "complete")

    @application.post("/tasks/{task_id}/fail", responses=errors)
    async def fail_task(task_id: str, update: TaskFailure) -> Task:
        return store.update(task_id, update.worker_id, "fail", update.error)

    return application


app = create_app()
