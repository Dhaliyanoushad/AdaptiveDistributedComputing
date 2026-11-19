"""Deterministic scheduling/recovery and actual ASGI image retry contracts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

from master.models import Heartbeat, TaskInput, WorkerRegistration
from master.scheduling import SchedulerSettings
from master.task_store import TaskStore, StoreError
from master.main import create_app
import test_master_images


class SchedulingRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.store = TaskStore(clock=lambda:self.now, utc_clock=lambda:datetime(2026,11,19,tzinfo=timezone.utc)+timedelta(seconds=self.now))
        self.tokens = {}

    def register(self, name):
        self.store.register(WorkerRegistration(worker_id=name,hostname=name),session_aware=True)
        self.tokens[name] = self.store.session_token(name)

    def beat(self, name, cpu=10, ram=20, available=4096):
        self.store.heartbeat(Heartbeat(worker_id=name,cpu_percent=cpu,ram_percent=ram,available_ram_mb=available),self.tokens[name])

    def submit(self):
        return self.store.submit([TaskInput(operation='dummy')])[0]

    def start(self, task):
        owner = self.store.get_task(task.task_id).assigned_worker
        self.store.poll(owner,self.tokens[owner])
        self.store.update(task.task_id,owner,'start',token=self.tokens[owner],assignment=self.store.assignment_token(task.task_id))

    def finish(self, task, action='complete', retryable=False):
        owner = self.store.get_task(task.task_id).assigned_worker
        return self.store.update(task.task_id,owner,action,error='test failure',token=self.tokens[owner],
            assignment=self.store.assignment_token(task.task_id),retryable=retryable)

    def adaptive(self, **kwargs):
        self.store.settings = SchedulerSettings(mode='adaptive',**kwargs)
        self.register('a')
        self.register('b')

    def test_static_round_robin_baseline(self):
        self.register('a'); self.register('b')
        self.assertEqual([task.assigned_worker for task in self.store.submit([TaskInput(operation='dummy')]*3)],['a','b',None])

    def test_low_cpu_ram_worker_wins(self):
        self.adaptive()
        self.beat('a',95,95,128)
        self.beat('b',5,10,4096)
        task = self.submit()
        self.assertEqual(task.assigned_worker,'b')
        self.assertEqual(task.attempt_history[0]['reason'],'resource_score')

    def test_missing_metrics_falls_back_to_round_robin(self):
        self.adaptive()
        task = self.submit()
        self.assertEqual(task.assigned_worker,'a')
        self.assertEqual(task.attempt_history[0]['reason'],'missing_metrics_round_robin')

    def test_stale_metrics_not_compared_with_fresh_metrics(self):
        self.adaptive()
        self.beat('a',0,0,4096)
        self.now = 9
        self.beat('b',90,90,256)
        self.assertEqual(self.submit().assigned_worker,'b')

    def test_all_stale_uses_fallback(self):
        self.adaptive()
        self.beat('a'); self.beat('b')
        self.now = 9
        self.assertEqual(self.submit().attempt_history[0]['reason'],'missing_metrics_round_robin')

    def test_insufficient_ram_waits_without_losing_pending_task(self):
        self.adaptive()
        self.beat('a',available=1); self.beat('b',available=1)
        task = self.submit()
        self.assertEqual(task.status,'pending')
        self.beat('b',available=4096)
        self.assertEqual(self.store.get_task(task.task_id).assigned_worker,'b')

    def test_adaptive_requires_sessions(self):
        self.store.settings = SchedulerSettings(mode='adaptive')
        self.store.register(WorkerRegistration(worker_id='legacy',hostname='host'))
        self.assertEqual(self.submit().status,'pending')

    def test_busy_and_offline_workers_are_excluded(self):
        self.adaptive()
        self.beat('a'); self.beat('b')
        first = self.submit()
        self.assertNotEqual(self.submit().assigned_worker,first.assigned_worker)
        self.now = 11
        self.store.recover_timeouts()
        self.assertTrue(all(t.status == 'pending' for t in self.store.list_tasks()))

    def test_fairness_bounds_skipped_eligible_worker(self):
        self.adaptive(fairness_max_skips=2)
        self.beat('a',0,0,4096); self.beat('b',100,100,128)
        assigned = []
        for _ in range(3):
            task = self.submit(); assigned.append(task.assigned_worker)
            self.start(task); self.finish(task)
        self.assertEqual(assigned,['a','a','b'])

    def test_processing_history_used_after_three_samples(self):
        self.adaptive(cpu_weight=0,ram_weight=0,available_weight=0,load_weight=0,history_weight=1)
        self.beat('a'); self.beat('b')
        self.store._durations = {'a':[10,10,10],'b':[1,1,1]}
        self.assertEqual(self.submit().assigned_worker,'b')

    def test_metric_changes_do_not_migrate_running_work(self):
        self.adaptive()
        self.beat('a'); self.beat('b')
        task = self.submit(); self.start(task)
        old = self.store.assignment_token(task.task_id)
        self.beat(task.assigned_worker,100,100,128)
        self.assertEqual(self.store.get_task(task.task_id).assigned_worker,task.assigned_worker)
        self.assertEqual(self.store.assignment_token(task.task_id),old)

    def test_assigned_timeout_requeues_once_and_reassigns(self):
        self.register('a'); self.register('b')
        task = self.submit()
        old = self.store.assignment_token(task.task_id)
        self.now = 9; self.beat('b')
        self.now = 11
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _:self.store.recover_timeouts(),range(30)))
        current = self.store.get_task(task.task_id)
        self.assertEqual((current.assigned_worker,current.attempt_count),('b',2))
        self.assertNotEqual(self.store.assignment_token(task.task_id),old)
        self.assertEqual(len(current.attempt_history),2)
        self.start(current); self.finish(current)
        self.assertEqual(self.store.get_task(task.task_id).status,'completed')

    def test_running_timeout_and_no_online_workers_preserve_pending(self):
        self.register('a')
        task = self.submit(); self.start(task)
        self.now = 11; self.store.recover_timeouts()
        self.assertEqual(self.store.get_task(task.task_id).status,'pending')
        self.store.recover_timeouts()
        self.assertEqual(list(self.store.pending),[task.task_id])
        self.register('b')
        self.assertEqual(self.store.get_task(task.task_id).assigned_worker,'b')

    def test_retry_limit_and_permanent_failure(self):
        self.register('a')
        task = self.submit()
        for index in range(3):
            self.start(task)
            current = self.finish(task,'fail',True)
        self.assertEqual((current.status,current.attempt_count),('failed',3))
        self.assertEqual([a['outcome'] for a in current.attempt_history],['retry','retry','failed'])
        other = self.submit(); self.start(other)
        self.assertEqual(self.finish(other,'fail').status,'failed')

    def test_stale_assignment_same_worker_cannot_finish_retry(self):
        self.register('a')
        task = self.submit(); self.start(task)
        old = self.store.assignment_token(task.task_id)
        self.finish(task,'fail',True)
        with self.assertRaises(StoreError):
            self.store.update(task.task_id,'a','complete',token=self.tokens['a'],assignment=old)
        with self.assertRaises(StoreError):
            self.store.update(task.task_id,'a','start',token=self.tokens['a'])
        self.start(task)
        complete = self.finish(task)
        self.assertEqual(self.finish(task).completed_at,complete.completed_at)

    def test_reconnect_does_not_restore_previous_assignment(self):
        self.register('a')
        task = self.submit(); self.start(task)
        old_session, old_assignment = self.tokens['a'], self.store.assignment_token(task.task_id)
        self.now = 11; self.store.recover_timeouts(); self.register('a')
        for session in [old_session,self.tokens['a']]:
            with self.assertRaises(StoreError):
                self.store.update(task.task_id,'a','complete',token=session,assignment=old_assignment)
        self.assertEqual(self.store.get_task(task.task_id).attempt_count,2)

    def test_concurrent_polling_delivers_one_generation(self):
        self.register('a')
        task = self.submit()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _:self.store.poll_assignment('a',self.tokens['a']),range(40)))
        self.assertEqual(sum(t is not None for t,g in results),1)

    def test_invalid_settings(self):
        for kwargs in [{'mode':'ml'},{'max_attempts':0},{'metrics_max_age':0},{'cpu_weight':-1},
                       {'ram_target_mb':float('nan')},{'fairness_max_skips':0},
                       dict.fromkeys(['cpu_weight','ram_weight','available_weight','load_weight','history_weight'],0)]:
            with self.subTest(settings=kwargs), self.assertRaises(ValueError):
                SchedulerSettings(**kwargs)

    def test_legacy_timeout_is_terminal_not_insecure_retry(self):
        self.store.register(WorkerRegistration(worker_id='legacy',hostname='host'))
        task = self.submit()
        self.now = 11; self.store.recover_timeouts()
        self.assertEqual(self.store.get_task(task.task_id).status,'failed')

    def test_recovered_task_does_not_downgrade_to_legacy_worker(self):
        self.register('a')
        task = self.submit()
        self.now = 9
        self.store.register(WorkerRegistration(worker_id='legacy',hostname='host'))
        self.now = 11; self.store.recover_timeouts()
        self.assertEqual(self.store.get_task(task.task_id).status,'pending')
        self.register('b')
        self.assertEqual(self.store.get_task(task.task_id).assigned_worker,'b')


class ImageRecoveryHTTPTests(unittest.IsolatedAsyncioTestCase):
    raw = test_master_images.ImageHTTPTests.raw

    async def test_image_retry_bytes_and_stale_result_integrity(self):
        now = [0.0]
        store = TaskStore(clock=lambda:now[0])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.app = create_app(store_override=store,input_dir=root/'in',output_dir=root/'out')
            tokens = {}
            for worker in ['a','b']:
                status, body, headers = await self.raw('POST','/workers/register',
                    json.dumps({'worker_id':worker,'hostname':worker}).encode(),extra_headers={b'x-worker-protocol':b'session-v1'})
                self.assertEqual(status,201)
                tokens[worker] = dict(headers)[b'x-worker-session']
            body, mime = test_master_images.multipart({'operation':'grayscale'},[('files','x.png',test_master_images.picture(),'image/png')])
            status, data, _ = await self.raw('POST','/images/tasks',body,mime)
            self.assertEqual(status,201)
            task = json.loads(data)[0]; task_id = task['task_id']
            async def poll(worker):
                status,data,_ = await self.raw('POST',f'/workers/{worker}/next-task',extra_headers={b'x-worker-session':tokens[worker]})
                self.assertEqual(status,200)
                return json.loads(data)['assignment_token'].encode()
            old = await poll('a')
            headers_a = {b'x-worker-session':tokens['a'],b'x-task-assignment':old}
            self.assertEqual((await self.raw('POST',f'/tasks/{task_id}/start',b'{"worker_id":"a"}',extra_headers=headers_a))[0],200)
            original = store.input_files[task_id].read_bytes()
            now[0] = 9
            store.heartbeat(Heartbeat(worker_id='b'),tokens['b'].decode())
            now[0] = 11; store.recover_timeouts()
            new = await poll('b')
            headers_b = {b'x-worker-session':tokens['b'],b'x-task-assignment':new}
            self.assertEqual((await self.raw('POST',f'/tasks/{task_id}/start',b'{"worker_id":"b"}',extra_headers=headers_b))[0],200)
            status,source,_ = await self.raw('GET',f'/tasks/{task_id}/input?worker_id=b',extra_headers=headers_b)
            self.assertEqual((status,source),(200,original))
            executable = Path(__file__).resolve().parents[1]/'worker/.venv/Scripts/python.exe'
            code = 'import sys; from worker.image_processing import process_image; sys.stdout.buffer.write(process_image(sys.stdin.buffer.read(),"grayscale",{}))'
            output = subprocess.run([str(executable),'-c',code],input=source,capture_output=True,check=True,timeout=30).stdout
            body,mime = test_master_images.multipart({'worker_id':'a'},[('file','result.png',output,'image/png')])
            self.assertEqual((await self.raw('POST',f'/tasks/{task_id}/result',body,mime,headers_a))[0],409)
            self.assertFalse((root/'out').exists())
            body,mime = test_master_images.multipart({'worker_id':'b'},[('file','result.png',output,'image/png')])
            self.assertEqual((await self.raw('POST',f'/tasks/{task_id}/result',body,mime,headers_b))[0],200)
            self.assertEqual((await self.raw('POST',f'/tasks/{task_id}/result',body,mime,headers_b))[0],200)
            stale,mime = test_master_images.multipart({'worker_id':'a'},[('file','result.png',output,'image/png')])
            self.assertEqual((await self.raw('POST',f'/tasks/{task_id}/result',stale,mime,headers_a))[0],409)
            self.assertEqual(store.result_files[task_id].read_bytes(),output)
            self.assertEqual(len(list((root/'out').iterdir())),1)
            status,data,_ = await self.raw('GET',f'/tasks/{task_id}/result/download')
            self.assertEqual((status,data),(200,output))
            self.assertEqual(len(json.loads((await self.raw('GET',f'/tasks/{task_id}/attempts'))[1])),2)
            self.assertEqual(json.loads((await self.raw('GET','/scheduler'))[1])['configuration']['mode'],'static')
