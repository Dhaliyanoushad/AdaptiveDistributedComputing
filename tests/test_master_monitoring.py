"""Controlled clocks, real ASGI contracts and thread-safe session fencing."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
import unittest
from unittest.mock import patch

from master.main import create_app
from master.models import Heartbeat, TaskInput, WorkerRegistration
from master.monitoring import timeout_loop, positive_setting
from master.task_store import TaskStore, StoreError
import test_master_images


class MonitoringTests(unittest.IsolatedAsyncioTestCase):
    raw = test_master_images.ImageHTTPTests.raw

    def setUp(self):
        self.now = 0.0
        self.store = TaskStore(clock=lambda: self.now,
            utc_clock=lambda: datetime(2026, 11, 19, tzinfo=timezone.utc) + timedelta(seconds=self.now))
        self.app = create_app(store_override=self.store)

    async def api(self, method, path, data=None, token=None, protocol=None):
        headers = {}
        if token:
            headers[b'x-worker-session'] = token.encode()
        if protocol:
            headers[b'x-worker-protocol'] = protocol.encode()
        status, body, response_headers = await self.raw(method, path, json.dumps(data or {}).encode(), extra_headers=headers)
        return status, json.loads(body), dict(response_headers)

    async def register(self, name='a', aware=True):
        status, body, headers = await self.api('POST','/workers/register', {'worker_id':name,'hostname':'host'},
                                              protocol='session-v1' if aware else None)
        self.assertEqual(status, 201)
        return headers.get(b'x-worker-session', b'').decode()

    async def test_metrics_schema_and_server_time(self):
        token = await self.register()
        self.now = 3
        status, worker, _ = await self.api('POST','/workers/heartbeat', {'worker_id':'a', 'cpu_percent':25,
            'ram_percent':60.5,'available_ram_mb':1024, 'timestamp':'2099-01-01T00:00:00Z'},token)
        self.assertEqual(status, 200)
        self.assertEqual(worker['cpu_percent'],25)
        self.assertEqual(worker['last_seen'],'2026-11-19T00:00:03Z')
        self.assertEqual(worker['status'],'online')
        records = (await self.api('GET','/workers'))[1]
        self.assertEqual(records,[worker])
        self.assertNotIn(token, json.dumps(records))
        self.assertEqual((await self.api('GET','/workers/a'))[1],worker)

    async def test_invalid_heartbeats_do_not_refresh_seen(self):
        token = await self.register()
        for changes in [{'cpu_percent':-1},{'cpu_percent':101},{'ram_percent':True},
                        {'available_ram_mb':-1},{'cpu_percent':'20'}, {'timestamp':'invalid'}, {'extra':1}]:
            self.now = 1
            self.assertEqual((await self.api('POST','/workers/heartbeat',{'worker_id':'a',**changes},token))[0],422)
        self.assertEqual(self.store._seen['a'],0)
        self.assertEqual((await self.api('POST','/workers/heartbeat',{'worker_id':'unknown'}))[0],404)
        self.assertEqual((await self.api('GET','/workers/unknown'))[0],404)

    async def test_null_metrics_keep_heartbeat_alive(self):
        token = await self.register()
        self.now = 5
        self.assertEqual((await self.api('POST','/workers/heartbeat',{'worker_id':'a'},token))[0],200)
        self.assertIsNone(self.store.get_worker('a').cpu_percent)
        self.now = 15
        self.store.expire_workers()
        self.assertEqual(self.store.get_worker('a').status,'online')
        self.now += .001
        self.store.expire_workers()
        self.assertEqual(self.store.get_worker('a').status,'offline')

    async def test_nonfinite_metrics_rejected(self):
        from pydantic import ValidationError
        for value in [float('nan'),float('inf'),float('-inf')]:
            with self.assertRaises(ValidationError):
                Heartbeat(worker_id='a',cpu_percent=value)

    async def test_idle_reconnection_can_receive_new_work(self):
        old = await self.register()
        self.now = 11
        self.store.expire_workers()
        token = await self.register()
        task = self.store.submit([TaskInput(operation='dummy')])[0]
        self.assertEqual(self.store.poll('a',token).task_id,task.task_id)
        assignment = self.store.assignment_token(task.task_id)
        self.store.update(task.task_id,'a','start',token=token,assignment=assignment)
        self.assertEqual(self.store.update(task.task_id,'a','complete',token=token,assignment=assignment).status,'completed')
        self.assertNotEqual(token,old)

    async def test_duplicate_online_session_is_rejected(self):
        token = await self.register()
        self.assertEqual((await self.api('POST','/workers/register', {'worker_id':'a','hostname':'hijack'}, protocol='session-v1'))[0],409)
        self.assertEqual(self.store.session_token('a'),token)
        for wrong in [None,'wrong']:
            self.assertEqual((await self.api('POST','/workers/heartbeat',{'worker_id':'a'},wrong))[0],401)
            self.assertEqual((await self.api('POST','/workers/a/next-task',token=wrong))[0],401)

    async def test_offline_reconnect_rotates_token_and_rejects_old_session(self):
        old = await self.register()
        self.now = 11
        self.store.expire_workers()
        self.assertEqual((await self.api('POST','/workers/heartbeat',{'worker_id':'a'},old))[0],409)
        new = await self.register()
        self.assertNotEqual(new,old)
        self.assertEqual((await self.api('POST','/workers/heartbeat',{'worker_id':'a'},old))[0],401)
        self.assertEqual((await self.api('POST','/workers/heartbeat',{'worker_id':'a'},new))[0],200)

    async def test_legacy_identity_cannot_be_upgraded_or_reconnected(self):
        await self.register(aware=False)
        self.now = 11
        self.store.expire_workers()
        self.assertEqual((await self.api('POST','/workers/register',{'worker_id':'a','hostname':'host'},protocol='session-v1'))[0],409)

    async def test_old_task_is_not_recovered_by_new_session(self):
        old = await self.register()
        task = self.store.submit([TaskInput(operation='dummy')])[0]
        self.store.poll('a',old)
        self.store.update(task.task_id,'a','start',token=old,assignment=self.store.assignment_token(task.task_id))
        self.now = 11
        self.store.expire_workers()
        new = await self.register()
        for token, code in [(old,401),(new,409)]:
            for action in ['start','complete','fail']:
                self.assertEqual((await self.api('POST',f'/tasks/{task.task_id}/{action}',
                    {'worker_id':'a', **({'error':'stale'} if action == 'fail' else {})},token))[0],code)
            with self.assertRaises(StoreError):
                self.store.input_path(task.task_id,'a',token)
            with self.assertRaises(StoreError):
                self.store.accept_result(task.task_id,'a',b'png',None,token)
        # Phase 5 permits a new assignment, never ownership of the old generation.
        self.assertEqual(self.store.get_task(task.task_id).status,'assigned')
        self.assertEqual(self.store.get_task(task.task_id).attempt_count,2)
        self.assertEqual(self.store.poll('a',new).task_id,task.task_id)

    async def test_offline_workers_are_not_eligible(self):
        await self.register()
        self.now = 11
        self.store.expire_workers()
        task = self.store.submit([TaskInput(operation='dummy')])[0]
        self.assertEqual(task.status,'pending')
        await self.register('b')
        self.assertEqual(self.store.get_task(task.task_id).assigned_worker,'b')

    async def test_periodic_timeout_loop_without_get_requests(self):
        await self.register()
        calls = []
        async def sleep(interval):
            calls.append(interval)
            self.now = 11
            if len(calls) == 2:
                raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await timeout_loop(self.store,1,sleep)
        self.assertEqual(self.store.workers['a'].status,'offline')
        self.assertEqual(calls,[1,1])

    async def test_lifespan_starts_and_cleans_up_sweeper(self):
        async with self.app.router.lifespan_context(self.app):
            task = self.app.state.timeout_task
            await asyncio.sleep(0)
            self.assertFalse(task.done())
        self.assertTrue(task.cancelled())

    async def test_concurrent_heartbeats_polls_and_completion(self):
        token = await self.register()
        task = self.store.submit([TaskInput(operation='dummy')])[0]
        def poll_or_beat(index):
            if index % 2:
                self.store.heartbeat(Heartbeat(worker_id='a',cpu_percent=1),token)
                return None
            return self.store.poll('a',token)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(poll_or_beat,range(40)))
        self.assertEqual(sum(item is not None for item in results),1)
        assignment = self.store.assignment_token(task.task_id)
        self.store.update(task.task_id,'a','start',token=token,assignment=assignment)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _:self.store.update(task.task_id,'a','complete',token=token,assignment=assignment),range(20)))
        self.assertTrue(all(item.status == 'completed' for item in results))

    async def test_session_fences_image_http_routes(self):
        token = await self.register()
        task = self.store.submit([TaskInput(operation='dummy')])[0]
        self.assertEqual((await self.api('GET',f'/tasks/{task.task_id}/input?worker_id=a',token='wrong'))[0],401)

    async def test_timeout_settings_reject_invalid_values(self):
        for value in ['0','-1','nan','inf','bad']:
            with patch.dict('os.environ',{'WORKER_TIMEOUT':value}), self.assertRaises(ValueError):
                positive_setting('WORKER_TIMEOUT',10)
