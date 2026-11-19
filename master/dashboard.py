"""Public, read-only dashboard stream. No worker credentials are serialized."""
import asyncio
import json
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder


def dashboard_origins() -> list[str]:
    values = [value.strip() for value in os.environ.get('CORS_ALLOWED_ORIGINS',
        'http://127.0.0.1:5173,http://localhost:5173').split(',') if value.strip()]
    for value in values:
        parsed = urlsplit(value)
        parsed.port  # Validate explicit port syntax/range as well as the hostname.
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('CORS_ALLOWED_ORIGINS must contain explicit HTTP(S) origins without paths or credentials')
    return list(dict.fromkeys(values))


def public_snapshot(store) -> dict:
    # Snapshot copying is protected; encoding and all network operations happen outside the lock.
    with store._lock:
        data = {'workers':store.list_workers(), 'tasks':store.list_tasks(), 'scheduler':store.scheduler_info()}
    return jsonable_encoder(data)


async def stream_dashboard(websocket, store, origins: list[str], interval: float = 2) -> None:
    if websocket.headers.get('origin') not in origins:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    previous = None
    try:
        while True:
            snapshot = public_snapshot(store)
            encoded = json.dumps({'type':'snapshot','data':snapshot},sort_keys=True,allow_nan=False)
            if encoded != previous:
                await asyncio.wait_for(websocket.send_text(encoded),timeout=5)
                previous = encoded
            try:
                await asyncio.wait_for(websocket.receive_text(),timeout=interval)
            except asyncio.TimeoutError:
                continue
            # Ignore client messages. Never expose mutation commands; bound message-driven snapshots.
            await asyncio.sleep(interval)
    except (WebSocketDisconnect, OSError, asyncio.TimeoutError):
        return


def dashboard_router(store, origins: list[str]) -> APIRouter:
    router = APIRouter()
    @router.websocket('/ws/dashboard')
    async def updates(websocket: WebSocket):
        await stream_dashboard(websocket,store,origins)
    return router
