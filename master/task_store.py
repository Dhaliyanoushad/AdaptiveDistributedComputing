"""Single-process registry, FIFO queue and static round-robin distribution."""

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from pathlib import Path
import secrets
import time

from master.models import Heartbeat, ImageTaskInput, Task, TaskInput, WorkerRegistration, WorkerRecord
from master.image_files import save_unique
from master.scheduling import SchedulerSettings, resource_score


class StoreError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class TaskStore:
    def __init__(self, *, timeout: float = 10, clock=time.monotonic, utc_clock=None, settings=None) -> None:
        self.workers: dict[str, WorkerRecord] = {}
        self.timeout = timeout
        self.clock = clock
        self.utc_clock = utc_clock or (lambda: datetime.now(timezone.utc))
        self._seen: dict[str, float] = {}
        self._sessions: dict[str, str] = {}
        self._task_sessions: dict[str, str | None] = {}
        self.settings = settings or SchedulerSettings()
        self._assignments: dict[str, str] = {}
        self._metrics_seen: dict[str, float] = {}
        self._skips: dict[str, int] = {}
        self._durations: dict[str, list[float]] = {}
        self._started: dict[str, float] = {}
        self.tasks: dict[str, Task] = {}
        self.pending: deque[str] = deque()
        self._active: dict[str, str] = {}
        self._delivered: set[str] = set()
        self._next_worker = 0
        self._lock = RLock()
        self.input_files: dict[str, Path] = {}
        self.result_files: dict[str, Path] = {}

    def register(self, worker: WorkerRegistration, *, session_aware: bool = False) -> WorkerRegistration:
        with self._lock:
            if worker.worker_id in self.workers:
                self.expire_workers()
                if (self.workers[worker.worker_id].status != "offline" or not session_aware
                        or worker.worker_id not in self._sessions):
                    raise StoreError(409, "Worker ID already registered")
            self.workers[worker.worker_id] = WorkerRecord(**worker.model_dump(), last_seen=self.utc_clock())
            self._seen[worker.worker_id] = self.clock()
            self._metrics_seen.pop(worker.worker_id, None)
            if session_aware:
                self._sessions[worker.worker_id] = secrets.token_urlsafe(32)
            self._distribute()
            return worker.model_copy(deep=True)

    def session_token(self, worker_id: str) -> str:
        with self._lock:
            return self._sessions[worker_id]

    def authorize(self, worker_id: str, token: str | None, task_id: str | None = None,
                  assignment: str | None = None) -> None:
        self.expire_workers()
        if worker_id not in self.workers:
            raise StoreError(404, "Worker not registered")
        if worker_id in self._sessions:
            expected = self._sessions[worker_id]
            if not token or not secrets.compare_digest(token, expected):
                raise StoreError(401, "Invalid worker session")
            if task_id is not None and self._task_sessions.get(task_id) != expected:
                raise StoreError(409, "Task belongs to another worker session")
            if task_id is not None and (not assignment or not secrets.compare_digest(assignment, self._assignments.get(task_id,''))):
                raise StoreError(409, "Missing or stale assignment token")
        if self.workers[worker_id].status != "online":
            raise StoreError(409, "Worker is offline; register a new session")

    def heartbeat(self, heartbeat: Heartbeat, token: str | None) -> WorkerRecord:
        with self._lock:
            self.expire_workers()
            self.authorize(heartbeat.worker_id, token)
            worker = self.workers[heartbeat.worker_id]
            worker.last_seen = self.utc_clock()
            self._seen[heartbeat.worker_id] = self.clock()
            self._metrics_seen[heartbeat.worker_id] = self.clock()
            for field in ("cpu_percent", "ram_percent", "available_ram_mb"):
                setattr(worker, field, getattr(heartbeat, field))
            self._distribute()
            return worker.model_copy(deep=True)

    def expire_workers(self) -> None:
        with self._lock:
            now = self.clock()
            for worker_id, worker in self.workers.items():
                if worker.status == 'online' and now - self._seen[worker_id] > self.timeout:
                    worker.status = "offline"
                    task_id = self._active.get(worker_id)
                    if task_id:
                        self._retry_or_fail(self.tasks[task_id], 'heartbeat_timeout', retryable=True)

    def _retry_or_fail(self, task: Task, reason: str, *, retryable: bool) -> None:
        old_worker = task.assigned_worker
        now = self.utc_clock()
        task.attempt_history[-1].update(outcome='retry' if retryable and task.attempt_count < self.settings.max_attempts and old_worker in self._sessions else 'failed',
                                        reason=reason, finished_at=now.isoformat())
        self._active.pop(old_worker,None)
        self._delivered.discard(task.task_id)
        self._started.pop(task.task_id,None)
        task.updated_at = now
        task.error = reason
        if retryable and task.attempt_count < self.settings.max_attempts and old_worker in self._sessions:
            task.status = 'pending'
            task.assigned_worker = None
            task.assigned_at = task.started_at = task.completed_at = task.failed_at = None
            if task.task_id not in self.pending:
                self.pending.append(task.task_id)
        else:
            task.status = 'failed'
            task.failed_at = now

    def recover_timeouts(self) -> None:
        with self._lock:
            self.expire_workers()
            self._distribute()

    def assignment_token(self, task_id: str) -> str:
        with self._lock:
            return self._assignments[task_id]

    def poll_assignment(self, worker_id: str, token: str | None) -> tuple[Task | None, str | None]:
        with self._lock:
            task = self.poll(worker_id,token)
            return task, self._assignments[task.task_id] if task and worker_id in self._sessions else None

    def scheduler_info(self) -> dict:
        with self._lock:
            return {'configuration':self.settings.model_dump(), 'pending_count':len(self.pending),
                    'workers':{key:{'load':int(key in self._active), 'fairness_skips':self._skips.get(key,0),
                        'completed_samples':len(self._durations.get(key,[])),
                        'mean_completion_seconds':sum(self._durations[key])/len(self._durations[key]) if self._durations.get(key) else None}
                        for key in self.workers}}

    def get_worker(self, worker_id: str) -> WorkerRecord:
        with self._lock:
            if worker_id not in self.workers:
                raise StoreError(404, "Worker not registered")
            return self.workers[worker_id].model_copy(deep=True)

    def list_workers(self) -> list[WorkerRecord]:
        with self._lock:
            return [worker.model_copy(deep=True) for worker in self.workers.values()]

    def submit(self, batch: list[TaskInput | ImageTaskInput]) -> list[Task]:
        with self._lock:
            ids = []
            for item in batch:
                now = self.utc_clock()
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
        self.expire_workers()
        worker_ids = list(self.workers)
        while self.pending and worker_ids:
            chosen = None
            for offset in range(len(worker_ids)):
                index = (self._next_worker + offset) % len(worker_ids)
                if (worker_ids[index] not in self._active and self.workers[worker_ids[index]].status == "online"
                        and (self.tasks[self.pending[0]].attempt_count == 0 or worker_ids[index] in self._sessions)):
                    chosen = index
                    break
            if chosen is None:
                return
            policy_reason, score = 'round_robin', None
            if self.settings.mode == 'adaptive':
                candidates = [key for key in worker_ids if key not in self._active and self.workers[key].status == 'online' and key in self._sessions]
                fresh = [key for key in candidates if self.clock()-self._metrics_seen.get(key,float('-inf')) <= self.settings.metrics_max_age
                         and all(getattr(self.workers[key],field) is not None for field in ('cpu_percent','ram_percent','available_ram_mb'))]
                eligible = [key for key in fresh if self.workers[key].available_ram_mb >= self.settings.min_available_ram_mb]
                fallback = not fresh
                pool = eligible if fresh else candidates
                if not pool:
                    return
                rotated = worker_ids[self._next_worker:]+worker_ids[:self._next_worker]
                ordered = [key for key in rotated if key in pool]
                scores = {key:resource_score(self.workers[key], int(key in self._active),
                    sum(self._durations[key])/len(self._durations[key]) if len(self._durations.get(key,[])) >= self.settings.history_min_samples else None,self.settings)
                    for key in eligible}
                overdue = [key for key in ordered if self._skips.get(key,0) >= self.settings.fairness_max_skips]
                selected = overdue[0] if overdue else (ordered[0] if fallback else max(ordered,key=lambda key:scores[key]))
                chosen = worker_ids.index(selected)
                score = scores.get(selected)
                policy_reason = 'fairness' if overdue else ('missing_metrics_round_robin' if fallback else 'resource_score')
                for key in pool:
                    self._skips[key] = 0 if key == selected else self._skips.get(key,0)+1
            worker_id = worker_ids[chosen]
            self._next_worker = (chosen + 1) % len(worker_ids)
            task = self.tasks[self.pending.popleft()]
            task.status = "assigned"
            task.assigned_worker = worker_id
            task.attempt_count += 1
            task.assigned_at = task.updated_at = self.utc_clock()
            self._active[worker_id] = task.task_id
            self._task_sessions[task.task_id] = self._sessions.get(worker_id)
            self._assignments[task.task_id] = secrets.token_urlsafe(32)
            task.error = None
            task.attempt_history.append({'attempt':task.attempt_count,'worker_id':worker_id,
                'assigned_at':self.utc_clock().isoformat(),'started_at':None,'finished_at':None,
                'outcome':'assigned','reason':policy_reason,'assignment_reason':policy_reason,'mode':self.settings.mode,'score':score})

    def poll(self, worker_id: str, token: str | None = None) -> Task | None:
        with self._lock:
            self.authorize(worker_id, token)
            if worker_id not in self.workers:
                raise StoreError(404, "Worker not registered")
            task_id = self._active.get(worker_id)
            if task_id is None or task_id in self._delivered:
                return None
            self.authorize(worker_id, token, task_id, self._assignments[task_id])
            self._delivered.add(task_id)
            return self.tasks[task_id].model_copy(deep=True)

    def update(self, task_id: str, worker_id: str, action: str, error: str | None = None,
               *, image_result: bool = False, token: str | None = None, assignment: str | None = None,
               retryable: bool = False) -> Task:
        with self._lock:
            task = self._get(task_id)
            self.authorize(worker_id, token, task_id, assignment)
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
                task.started_at = task.updated_at = self.utc_clock()
                self._started[task_id] = self.clock()
                task.attempt_history[-1].update(started_at=self.utc_clock().isoformat(),outcome='running')
            elif action in {"complete", "fail"}:
                if task.status != "running":
                    raise StoreError(409, "Only a running task can finish")
                now = self.utc_clock()
                task.updated_at = now
                if action == "complete":
                    task.status = "completed"
                    task.completed_at = now
                else:
                    self._retry_or_fail(task,error or 'processing_failure',retryable=retryable)
                    self._distribute()
                    return task.model_copy(deep=True)
                duration = max(0,self.clock()-self._started.pop(task_id,self.clock()))
                history = self._durations.setdefault(worker_id,[])
                history.append(duration)
                del history[:-100]
                task.attempt_history[-1].update(outcome='completed',finished_at=self.utc_clock().isoformat(),duration_seconds=duration)
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

    def input_path(self, task_id: str, worker_id: str, token: str | None = None, assignment: str | None = None) -> Path:
        with self._lock:
            task = self._get(task_id)
            self.authorize(worker_id, token, task_id, assignment)
            if worker_id not in self.workers:
                raise StoreError(404, "Worker not registered")
            if task.assigned_worker != worker_id or task.status not in {"assigned", "running"}:
                raise StoreError(409, "Only the active assigned worker may download input")
            if task_id not in self.input_files:
                raise StoreError(404, "Task has no image")
            return self.input_files[task_id]

    def accept_result(self, task_id: str, worker_id: str, data: bytes, directory: Path, token: str | None = None, assignment: str | None = None) -> Task:
        with self._lock:
            task = self._get(task_id)
            self.authorize(worker_id, token, task_id, assignment)
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
            try:
                return self.update(task_id, worker_id, "complete", image_result=True, token=token, assignment=assignment)
            except Exception:
                self.result_files.pop(task_id,None)
                path.unlink(missing_ok=True)
                raise

    def result_path(self, task_id: str) -> Path:
        with self._lock:
            task = self._get(task_id)
            if task.status != "completed" or task_id not in self.result_files:
                raise StoreError(404, "Completed image result not available")
            return self.result_files[task_id]
