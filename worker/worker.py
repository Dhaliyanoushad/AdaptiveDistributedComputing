"""Register once, poll for dummy tasks and report execution state."""

import math
import os
import socket
import sys
import time
from urllib.parse import quote, urlsplit

import requests

REQUEST_TIMEOUT = (3.05, 10)
SESSION_TOKEN = None
ASSIGNMENT_TOKEN = None


def session_headers() -> dict:
    if not SESSION_TOKEN:
        return {}
    headers = {"X-Worker-Session": SESSION_TOKEN}
    if ASSIGNMENT_TOKEN:
        headers['X-Task-Assignment'] = ASSIGNMENT_TOKEN
    return {"headers": headers}


def execute_image(master_url: str, task: dict, worker_id: str) -> None:
    # Lazy import preserves dummy-only use and script/module execution.
    try:
        from worker.image_processing import process_image, MAX_BYTES
    except ModuleNotFoundError:
        from image_processing import process_image, MAX_BYTES
    task_url = f"{master_url}/tasks/{quote(task['task_id'], safe='')}"
    with requests.get(f"{task_url}/input", params={"worker_id": worker_id},
                      timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=False, **session_headers()) as response:
        if response.status_code != 200:
            raise ValueError(f"Image download failed: HTTP {response.status_code}")
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ValueError("Downloaded image exceeds 10 MiB")
    output = process_image(bytes(data), task["operation"], task["payload"]["parameters"])
    response = requests.post(f"{task_url}/result", data={"worker_id": worker_id},
                             files={"file": ("result.png", output, "image/png")},
                             timeout=REQUEST_TIMEOUT, allow_redirects=False, **session_headers())
    if response.status_code != 200:
        raise ValueError(f"Result upload failed: HTTP {response.status_code}: {response.text[:200]}")


def post_update(url: str, payload: dict, expected_status: int = 200) -> requests.Response:
    response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT, allow_redirects=False, **session_headers())
    if response.status_code != expected_status:
        raise ValueError(f"HTTP {response.status_code}: {response.text[:500]}")
    return response


def run_worker(master_url: str, worker_id: str, poll_interval: float, task_delay: float) -> int:
    global ASSIGNMENT_TOKEN
    """No retry, recovery or heartbeat: communication failure stops the worker."""
    poll_url = f"{master_url}/workers/{quote(worker_id, safe='')}/next-task"
    while True:
        ASSIGNMENT_TOKEN = None
        response = post_update(poll_url, {})
        reply = response.json()
        task = reply["task"]
        if task is None:
            time.sleep(poll_interval)
            continue
        ASSIGNMENT_TOKEN = reply.get('assignment_token')
        task_id = task["task_id"]
        task_url = f"{master_url}/tasks/{quote(task_id, safe='')}"
        identity = {"worker_id": worker_id}
        post_update(f"{task_url}/start", identity)
        print(f"Task {task_id}: running", flush=True)
        if task["operation"] != "dummy":
            try:
                execute_image(master_url, task, worker_id)
            except (ValueError, OSError, KeyError) as exc:
                post_update(f"{task_url}/fail", {**identity, "error": str(exc)[:500] or "Image processing failed",
                    "retryable": isinstance(exc, (requests.RequestException, OSError))})
                print(f"Task {task_id}: failed: {exc}", flush=True)
            else:
                print(f"Task {task_id}: image completed", flush=True)
            continue
        time.sleep(task_delay)
        # Dummy tasks never execute payload contents as code or commands.
        if task["operation"] != "dummy" or task["payload"].get("fail") is True:
            post_update(f"{task_url}/fail", {**identity, "error": "Simulated dummy-task failure",
                "retryable": task["payload"].get('retryable') is True})
            print(f"Task {task_id}: failed (simulated)", flush=True)
        else:
            post_update(f"{task_url}/complete", identity)
            print(f"Task {task_id}: completed", flush=True)


def main() -> int:
    global SESSION_TOKEN, ASSIGNMENT_TOKEN
    SESSION_TOKEN = None
    ASSIGNMENT_TOKEN = None
    master_url = os.environ.get("MASTER_URL", "http://127.0.0.1:8000").strip().rstrip("/")
    try:
        parsed = urlsplit(master_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
            raise ValueError("expected an HTTP(S) base URL without a query or fragment")
        hostname = socket.gethostname()
        worker_id = os.environ.get("WORKER_ID", hostname).strip()
        if not worker_id:
            raise ValueError("WORKER_ID must not be empty")
        poll_interval = float(os.environ.get("POLL_INTERVAL", "1"))
        task_delay = float(os.environ.get("TASK_DELAY", "0.5"))
        heartbeat_interval = float(os.environ.get("HEARTBEAT_INTERVAL", "3"))
        heartbeat_timeout = float(os.environ.get("HEARTBEAT_HTTP_TIMEOUT", "2"))
        if any(not math.isfinite(value) or value <= 0 for value in [heartbeat_interval, heartbeat_timeout]):
            raise ValueError("Heartbeat interval and timeout must be finite and greater than zero")
        if not math.isfinite(poll_interval) or poll_interval <= 0:
            raise ValueError("POLL_INTERVAL must be finite and greater than zero")
        if not math.isfinite(task_delay) or task_delay < 0:
            raise ValueError("TASK_DELAY must be finite and nonnegative")
    except (ValueError, OSError) as exc:
        print(f"Worker configuration failed: {exc}", file=sys.stderr)
        return 1

    try:
        response = requests.post(
            f"{master_url}/workers/register",
            json={"worker_id": worker_id, "hostname": hostname},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
            headers={"X-Worker-Protocol": "session-v1"},
        )
        if response.status_code != 201:
            print(
                f"Registration failed: HTTP {response.status_code}: {response.text[:500]}",
                file=sys.stderr,
            )
            return 1
    except requests.RequestException as exc:
        print(f"Registration failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Registration successful: worker_id={worker_id!r}, hostname={hostname!r}", flush=True)
    token = response.headers.get("X-Worker-Session")
    SESSION_TOKEN = token if isinstance(token, str) and token else None
    try:
        if SESSION_TOKEN:
            try:
                from worker.monitoring import HeartbeatSender
            except ModuleNotFoundError:
                from monitoring import HeartbeatSender
            with HeartbeatSender(master_url, worker_id, SESSION_TOKEN, heartbeat_interval,
                                 (heartbeat_timeout, heartbeat_timeout)):
                return run_worker(master_url, worker_id, poll_interval, task_delay)
        # Compatibility with a Phase 1-3 master; no session-safe reconnection.
        return run_worker(master_url, worker_id, poll_interval, task_delay)
    except KeyboardInterrupt:
        print("Worker stopped. Wait for offline status before reconnecting; the master recovers eligible unfinished attempts.")
        return 0
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        print(f"Worker stopped after task communication failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
