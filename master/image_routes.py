"""HTTP byte transfers; no master filesystem paths are sent to workers."""

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from master.image_files import MAX_BYTES, inspect_image, save_unique
from master.models import ImageTaskInput, Task
from master.task_store import TaskStore


def parameters(operation: str, text: str) -> dict:
    try:
        values = json.loads(text)
        if not isinstance(values, dict):
            raise ValueError("parameters must be an object")
        allowed = {"grayscale": {}, "resize": {"width": (1, 4096), "height": (1, 4096)},
                   "gaussian_blur": {"kernel_size": (1, 99)},
                   "edge_detection": {"threshold1": (0, 255), "threshold2": (0, 255)}}[operation]
        defaults = {"gaussian_blur": {"kernel_size": 5},
                    "edge_detection": {"threshold1": 100, "threshold2": 200}}.get(operation, {})
        if set(values) - set(allowed):
            raise ValueError("Unknown operation parameters")
        values = defaults | values
        for key, (low, high) in allowed.items():
            if type(values.get(key)) is not int or not low <= values[key] <= high:
                raise ValueError(f"{key} must be an integer from {low} to {high}")
        if operation == "resize" and values["width"] * values["height"] > 16_000_000:
            raise ValueError("Resize exceeds 16 million pixels")
        if operation == "gaussian_blur" and values["kernel_size"] % 2 != 1:
            raise ValueError("kernel_size must be odd")
        if operation == "edge_detection" and values["threshold1"] > values["threshold2"]:
            raise ValueError("threshold1 must not exceed threshold2")
        return values
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


async def read_image(file: UploadFile, *, output: bool = False) -> tuple[bytes, tuple[int, int, str]]:
    try:
        suffix = Path(file.filename or "").suffix.lower()
        accepted = {".png"} if output else {".png", ".jpg", ".jpeg"}
        if suffix not in accepted or file.content_type not in ({"image/png"} if output else {"image/png", "image/jpeg"}):
            raise HTTPException(415, "Unsupported filename extension or content type")
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 10 MiB")
        try:
            info = inspect_image(data, output)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return data, info
    finally:
        await file.close()


def image_router(store: TaskStore, input_dir: Path, output_dir: Path) -> APIRouter:
    router = APIRouter()

    @router.post("/images/tasks", status_code=201)
    async def upload_images(
        files: list[UploadFile] = File(...),
        operation: Literal["grayscale", "resize", "gaussian_blur", "edge_detection"] = Form(...),
        params: str = Form("{}"),
    ) -> list[Task]:
        paths = []
        try:
            if not 1 <= len(files) <= 20:
                raise HTTPException(422, "Upload 1 to 20 images per batch")
            options = parameters(operation, params)
            items = []
            # Validate the entire batch before publishing any tasks.
            for file in files:
                data, (width, height, _) = await read_image(file)
                paths.append(save_unique(input_dir, data, ".img"))
                items.append(ImageTaskInput(operation=operation, payload={
                    "parameters": options, "width": width, "height": height,
                }))
            return store.submit_images(items, paths)
        except Exception:
            for path in paths:
                path.unlink(missing_ok=True)
            raise
        finally:
            for file in files:
                await file.close()

    @router.get("/tasks/{task_id}/input", responses={401: {"description": "Invalid session"},
                404: {"description": "Task or worker not found"}, 409: {"description": "Wrong owner, offline worker or old task session"}})
    async def download_input(task_id: str, worker_id: str, x_worker_session: str | None = Header(default=None),
                             x_task_assignment: str | None = Header(default=None)) -> FileResponse:
        return FileResponse(store.input_path(task_id, worker_id, x_worker_session, x_task_assignment), media_type="application/octet-stream")

    @router.post("/tasks/{task_id}/result", responses={401: {"description": "Invalid session"},
                 404: {"description": "Task or worker not found"}, 409: {"description": "Invalid owner/state/session"}})
    async def upload_result(task_id: str, worker_id: str = Form(...), file: UploadFile = File(...),
                            x_worker_session: str | None = Header(default=None),
                            x_task_assignment: str | None = Header(default=None)) -> Task:
        task = store.get_task(task_id)
        data, (width, height, mode) = await read_image(file, output=True)
        expected = task.payload.get("parameters", {})
        dimensions = (expected["width"], expected["height"]) if task.operation == "resize" else (
            task.payload.get("width"), task.payload.get("height"))
        if (width, height) != dimensions:
            raise HTTPException(422, "Result dimensions do not match the task")
        if task.operation in {"grayscale", "edge_detection"} and mode != "L":
            raise HTTPException(422, "Operation requires an 8-bit grayscale output")
        return store.accept_result(task_id, worker_id, data, output_dir, x_worker_session, x_task_assignment)

    @router.get("/tasks/{task_id}/result")
    async def view_result(task_id: str) -> FileResponse:
        return FileResponse(store.result_path(task_id), media_type="image/png")

    @router.get("/tasks/{task_id}/result/download")
    async def download_result(task_id: str) -> FileResponse:
        return FileResponse(store.result_path(task_id), media_type="image/png", filename=f"{task_id}.png")

    return router
