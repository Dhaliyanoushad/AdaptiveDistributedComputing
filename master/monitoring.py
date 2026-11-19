"""Lifecycle-owned periodic timeout sweeper."""
import asyncio
import math
import os


def positive_setting(name: str, default: float) -> float:
    value = float(os.environ.get(name, str(default)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return value


async def timeout_loop(store, interval: float, sleep=asyncio.sleep) -> None:
    while True:
        store.recover_timeouts()
        await sleep(interval)
