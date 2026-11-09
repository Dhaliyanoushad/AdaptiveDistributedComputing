"""Register once, poll for dummy tasks and report execution state."""

import math
import os
import socket
import sys
import time
from urllib.parse import quote, urlsplit

import requests

REQUEST_TIMEOUT = (3.05, 10)


def post_update(url: str, payload: dict, expected_status: int = 200) -> requests.Response:
    response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT, allow_redirects=False)
    if response.status_code != expected_status:
        raise ValueError(f"HTTP {response.status_code}: {response.text[:500]}")
    return response


def run_worker(master_url: str, worker_id: str, poll_interval: float, task_delay: float) -> int:
    """No retry, recovery or heartbeat: communication failure stops the worker."""
    poll_url = f"{master_url}/workers/{quote(worker_id, safe='')}/next-task"
    while True:
        response = post_update(poll_url, {})
        task = response.json()["task"]
        if task is None:
            time.sleep(poll_interval)
            continue
        task_id = task["task_id"]
        task_url = f"{master_url}/tasks/{quote(task_id, safe='')}"
        identity = {"worker_id": worker_id}
        post_update(f"{task_url}/start", identity)
        print(f"Task {task_id}: running", flush=True)
        time.sleep(task_delay)
        # Dummy tasks never execute payload contents as code or commands.
        if task["operation"] != "dummy" or task["payload"].get("fail") is True:
            post_update(f"{task_url}/fail", {**identity, "error": "Simulated dummy-task failure"})
            print(f"Task {task_id}: failed (simulated)", flush=True)
        else:
            post_update(f"{task_url}/complete", identity)
            print(f"Task {task_id}: completed", flush=True)


def main() -> int:
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
    try:
        return run_worker(master_url, worker_id, poll_interval, task_delay)
    except KeyboardInterrupt:
        print("Worker stopped. Reconnection is not supported; unfinished tasks remain assigned/running.")
        return 0
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        print(f"Worker stopped after task communication failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
