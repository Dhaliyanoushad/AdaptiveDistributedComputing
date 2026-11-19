"""Independent, bounded HTTP heartbeat thread with nonblocking psutil sampling."""
from datetime import datetime, timezone
import logging
import math
import threading

import psutil
import requests

logger = logging.getLogger(__name__)


def collect_metrics() -> dict:
    result = {"cpu_percent": None, "ram_percent": None, "available_ram_mb": None}
    try:
        value = float(psutil.cpu_percent(interval=None))
        if math.isfinite(value) and 0 <= value <= 100:
            result["cpu_percent"] = value
    except (psutil.Error, OSError, ValueError, TypeError):
        logger.warning("CPU metrics unavailable")
    try:
        memory = psutil.virtual_memory()
        percent, available = float(memory.percent), float(memory.available) / (1024 * 1024)
        if math.isfinite(percent) and 0 <= percent <= 100:
            result["ram_percent"] = percent
        if math.isfinite(available) and available >= 0:
            result["available_ram_mb"] = available
    except (psutil.Error, OSError, ValueError, TypeError):
        logger.warning("RAM metrics unavailable")
    return result


class HeartbeatSender:
    def __init__(self, url: str, worker_id: str, token: str, interval: float = 3,
                 timeout: tuple[float, float] = (2, 2), *, stop=None):
        self.url, self.worker_id, self.token = url, worker_id, token
        self.interval, self.timeout = interval, timeout
        self.stop = stop or threading.Event()
        self.thread = threading.Thread(target=self.run, name="worker-heartbeat", daemon=True)

    def send_once(self) -> None:
        response = requests.post(self.url + "/workers/heartbeat",
            json={"worker_id": self.worker_id, "timestamp": datetime.now(timezone.utc).isoformat(), **collect_metrics()},
            headers={"X-Worker-Session": self.token}, timeout=self.timeout, allow_redirects=False)
        if response.status_code != 200:
            raise ValueError(f"Heartbeat rejected: HTTP {response.status_code}")

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                self.send_once()
            except (requests.RequestException, ValueError) as exc:
                logger.warning("Heartbeat failed: %s", exc)
            if self.stop.wait(self.interval):
                break

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=sum(self.timeout) + 1)
