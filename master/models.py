"""Validated HTTP contracts for registration and dummy tasks."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class WorkerRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    worker_id: str = Field(strict=True, min_length=1, max_length=128)
    hostname: str = Field(strict=True, min_length=1, max_length=253)


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["dummy"]
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class TaskBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tasks: list[TaskInput] = Field(min_length=1, max_length=1000)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    worker_id: str = Field(strict=True, min_length=1, max_length=128)


class TaskFailure(TaskUpdate):
    error: str = Field(strict=True, min_length=1, max_length=500)


class Task(TaskInput):
    operation: Literal["dummy", "grayscale", "resize", "gaussian_blur", "edge_detection"]
    task_id: str
    status: Literal["pending", "assigned", "running", "completed", "failed"] = "pending"
    assigned_worker: str | None = None
    attempt_count: int = 0
    created_at: datetime
    updated_at: datetime
    assigned_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error: str | None = None


class TaskPoll(BaseModel):
    task: Task | None


class ImageTaskInput(BaseModel):
    operation: Literal["grayscale", "resize", "gaussian_blur", "edge_detection"]
    payload: dict[str, JsonValue]
