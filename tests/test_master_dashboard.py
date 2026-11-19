"""CORS policy and public WebSocket snapshots with no credential exposure."""
import asyncio
import json
import unittest
from unittest.mock import patch

from fastapi import WebSocketDisconnect
from master.main import create_app
from master.dashboard import dashboard_origins, public_snapshot, stream_dashboard
from master.models import WorkerRegistration, TaskInput
from master.task_store import TaskStore
import test_master_images


class DashboardAPITests(unittest.IsolatedAsyncioTestCase):
    raw = test_master_images.ImageHTTPTests.raw

    def setUp(self):
        self.app = create_app()

    async def test_allowed_cors_get(self):
        status,body,headers = await self.raw('GET','/workers',extra_headers={b'origin':b'http://127.0.0.1:5173'})
        self.assertEqual(status,200)
        self.assertEqual(dict(headers)[b'access-control-allow-origin'],b'http://127.0.0.1:5173')

    async def test_denied_origin_has_no_cors_permission(self):
        status,body,headers = await self.raw('GET','/workers',extra_headers={b'origin':b'https://untrusted.example'})
        self.assertEqual(status,200)
        self.assertNotIn(b'access-control-allow-origin',dict(headers))

    async def test_upload_preflight(self):
        status,body,headers = await self.raw('OPTIONS','/images/tasks',extra_headers={
            b'origin':b'http://localhost:5173',b'access-control-request-method':b'POST',b'access-control-request-headers':b'content-type'})
        self.assertEqual(status,200)
        self.assertIn(b'access-control-allow-origin',dict(headers))

    async def test_custom_origin_configuration(self):
        with patch.dict('os.environ',{'CORS_ALLOWED_ORIGINS':'http://192.168.1.10:5173'}):
            self.app = create_app()
        status,body,headers = await self.raw('GET','/health',extra_headers={b'origin':b'http://192.168.1.10:5173'})
        self.assertEqual(dict(headers)[b'access-control-allow-origin'],b'http://192.168.1.10:5173')

    async def test_invalid_origins_fail_configuration(self):
        for value in ['*','file:///tmp','http://localhost:5173/path','https://user:pass@host','null']:
            with self.subTest(origin=value),patch.dict('os.environ',{'CORS_ALLOWED_ORIGINS':value}), self.assertRaises(ValueError):
                dashboard_origins()

    async def test_snapshot_excludes_all_private_credentials(self):
        store = self.app.state.store
        store.register(WorkerRegistration(worker_id='a',hostname='host'),session_aware=True)
        task = store.submit([TaskInput(operation='dummy')])[0]
        text = json.dumps(public_snapshot(store))
        self.assertNotIn(store.session_token('a'),text)
        self.assertNotIn(store.assignment_token(task.task_id),text)
        self.assertNotIn('assignment_token',text)
        self.assertEqual(set(json.loads(text)),{'workers','tasks','scheduler'})


class FakeSocket:
    def __init__(self,origin='http://localhost:5173',receive=None):
        self.headers = {'origin':origin}
        self.sent = []
        self.accepted = False
        self.code = None
        self.receive = receive

    async def accept(self):
        self.accepted = True

    async def close(self,code):
        self.code = code

    async def send_text(self,text):
        self.sent.append(json.loads(text))

    async def receive_text(self):
        if self.receive:
            return await self.receive()
        raise WebSocketDisconnect()


class DashboardStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_network_send_does_not_hold_store_lock(self):
        store = TaskStore()
        socket = FakeSocket()
        async def send(text):
            self.assertFalse(store._lock._is_owned())
            socket.sent.append(json.loads(text))
        socket.send_text = send
        await stream_dashboard(socket,store,['http://localhost:5173'])
        self.assertEqual(len(socket.sent),1)

    async def test_initial_snapshot_and_disconnection(self):
        socket = FakeSocket()
        await stream_dashboard(socket,TaskStore(),['http://localhost:5173'])
        self.assertTrue(socket.accepted)
        self.assertEqual(len(socket.sent),1)
        self.assertEqual(socket.sent[0]['type'],'snapshot')

    async def test_origin_rejected_before_accept(self):
        socket = FakeSocket(origin='https://untrusted.example')
        await stream_dashboard(socket,TaskStore(),['http://localhost:5173'])
        self.assertFalse(socket.accepted)
        self.assertEqual(socket.code,1008)

    async def test_changed_state_is_published(self):
        store = TaskStore()
        calls = []
        async def receive():
            if calls:
                raise WebSocketDisconnect()
            calls.append(1)
            store.register(WorkerRegistration(worker_id='a',hostname='host'))
            return 'ignored'
        socket = FakeSocket(receive=receive)
        await stream_dashboard(socket,store,['http://localhost:5173'],interval=.001)
        self.assertEqual(len(socket.sent),2)
        self.assertEqual(socket.sent[1]['data']['workers'][0]['worker_id'],'a')

    async def test_unchanged_state_does_not_duplicate_frames(self):
        count = [0]
        async def receive():
            count[0]+=1
            if count[0]>1:
                raise WebSocketDisconnect()
            return 'ignored'
        socket = FakeSocket(receive=receive)
        await stream_dashboard(socket,TaskStore(),['http://localhost:5173'],interval=.001)
        self.assertEqual(len(socket.sent),1)
