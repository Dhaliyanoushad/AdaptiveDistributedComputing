"""Single-process registry, FIFO queue and static round-robin distribution."""

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from pathlib import Path

from master.models import ImageTaskInput, Task, TaskInput, WorkerRegistration
from master.image_files import save_unique


class StoreError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class TaskStore:
    def __init__(self) -> None:
        self.workers: dict[str, WorkerRegistration] = {}
        self.tasks: dict[str, Task] = {}
        self.pending: deque[str] = deque()
        self._active: dict[str, str] = {}
        self._delivered: set[str] = set()
        self._next_worker = 0
        self._lock = RLock()
        self.input_files: dict[str, Path] = {}
        self.result_files: dict[str, Path] = {}

    def register(self, worker: WorkerRegistration) -> WorkerRegistration:
        with self._lock:
            if worker.worker_id in self.workers:
                raise StoreError(409, "Worker ID already registered")
            self.workers[worker.worker_id] = worker.model_copy(deep=True)
            self._distribute()
            return worker.model_copy(deep=True)

    def list_workers(self) -> list[WorkerRegistration]:
        with self._lock:
            return [worker.model_copy(deep=True) for worker in self.workers.values()]

    def submit(self, batch: list[TaskInput | ImageTaskInput]) -> list[Task]:
        with self._lock:
            ids = []
            for item in batch:
                now = datetime.now(timezone.utc)
                task = Task(**item.model_dump(), task_id=str(uuid4()), created_at=now, updated_at=now)
                self.tasks[task.task_id] = task
                self.pending.append(task.task_id)
                ids.append(task.task_id)
            self._distribute()
            return [self.tasks[task_id].model_copy(deep=True) for task_id in ids]

    def list_tasks(self) -> list[Task]:
        with self._lock:
            return [task.model_copy(deep=True) for task in self.tasks.values()]

    def get_task(self, task_id: str) -> Task:
        with self._lock:
            return self._get(task_id).model_copy(deep=True)

    def _get(self, task_id: str) -> Task:
        if task_id not in self.tasks:
            raise StoreError(404, "Task not found")
        return self.tasks[task_id]

    def _distribute(self) -> None:
        """Called only with the lock held; registered idle workers are eligible."""
        worker_ids = list(self.workers)
        while self.pending and worker_ids:
            chosen = None
            for offset in range(len(worker_ids)):
                index = (self._next_worker + offset) % len(worker_ids)
                if worker_ids[index] not in self._active:
                    chosen = index
                    break
            if chosen is None:
                return
            worker_id = worker_ids[chosen]
            self._next_worker = (chosen + 1) % len(worker_ids)
            task = self.tasks[self.pending.popleft()]
            task.status = "assigned"
            task.assigned_worker = worker_id
            task.attempt_count += 1
            task.assigned_at = task.updated_at = datetime.now(timezone.utc)
            self._active[worker_id] = task.task_id

    def poll(self, worker_id: str) -> Task | None:
        with self._lock:
            if worker_id not in self.workers:
                raise StoreError(404, "Worker not registered")
            task_id = self._active.get(worker_id)
            if task_id is None or task_id in self._delivered:
                return None
            self._delivered.add(task_id)
            return self.tasks[task_id].model_copy(deep=True)

    def update(self, task_id: str, worker_id: str, action: str, error: str | None = None,
               *, image_result: bool = False) -> Task:
        with self._lock:
            task = self._get(task_id)
            if worker_id not in self.workers:
                raise StoreError(404, "Worker not registered")
            if task.assigned_worker != worker_id:
                raise StoreError(409, "Task is not assigned to this worker")
            if action == "complete" and task.operation != "dummy" and not image_result:
                raise StoreError(409, "Image tasks require a validated result upload")
            if action == "complete" and task.status == "completed":
                return task.model_copy(deep=True)
            if action == "start":
                if task.status != "assigned" or task_id not in self._delivered:
                    raise StoreError(409, "Only a polled assigned task can start")
                task.status = "running"
                task.started_at = task.updated_at = datetime.now(timezone.utc)
            elif action in {"complete", "fail"}:
                if task.status != "running":
                    raise StoreError(409, "Only a running task can finish")
                now = datetime.now(timezone.utc)
                task.updated_at = now
                if action == "complete":
                    task.status = "completed"
                    task.completed_at = now
                else:
                    task.status = "failed"
                    task.failed_at = now
                    task.error = error
                del self._active[worker_id]
                self._delivered.discard(task_id)
                self._distribute()
            else:
                raise ValueError("Unsupported task update action")
            return task.model_copy(deep=True)

    def submit_images(self, items: list[ImageTaskInput], paths: list[Path]) -> list[Task]:
        with self._lock:
            tasks = self.submit(items)
            self.input_files.update({task.task_id: path for task, path in zip(tasks, paths, strict=True)})
            return tasks

    def input_path(self, task_id: str, worker_id: str) -> Path:
        with self._lock:
            task = self._get(task_id)
            if worker_id not in self.workers:
                raise StoreError(404, "Worker not registered")
            if task.assigned_worker != worker_id or task.status not in {"assigned", "running"}:
                raise StoreError(409, "Only the active assigned worker may download input")
            if task_id not in self.input_files:
                raise StoreError(404, "Task has no image")
            return self.input_files[task_id]

    def accept_result(self, task_id: str, worker_id: str, data: bytes, directory: Path) -> Task:
        with self._lock:
            task = self._get(task_id)
            if worker_id not in self.workers:
                raise StoreError(404, "Worker not registered")
            if task.assigned_worker != worker_id:
                raise StoreError(409, "Task is not assigned to this worker")
            if task.operation == "dummy":
                raise StoreError(409, "Dummy tasks do not accept images")
            if task.status == "completed":
                if self.result_files[task_id].read_bytes() != data:
                    raise StoreError(409, "Completed image cannot be replaced")
                return task.model_copy(deep=True)
            if task.status != "running":
                raise StoreError(409, "Only a running image task can finish")
            path = save_unique(directory, data, ".png")
            self.result_files[task_id] = path
            return self.update(task_id, worker_id, "complete", image_result=True)

    def result_path(self, task_id: str) -> Path:
        with self._lock:
            task = self._get(task_id)
            if task.status != "completed" or task_id not in self.result_files:
                raise StoreError(404, "Completed image result not available")
            return self.result_files[task_id]
