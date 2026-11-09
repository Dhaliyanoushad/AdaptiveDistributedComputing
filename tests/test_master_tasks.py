"""Phase 2 API, round-robin and concurrent mutation checks."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import unittest

import test_master
from master.main import create_app


class TaskTests(unittest.IsolatedAsyncioTestCase):
    request = test_master.MasterTests.request
    register = test_master.MasterTests.register

    def setUp(self):
        self.app = create_app()

    async def post(self, path, body=None):
        return await self.request("POST", path, json.dumps(body or {}).encode())

    async def add_workers(self, *names):
        for name in names:
            self.assertEqual((await self.register({"worker_id": name, "hostname": name}))[0], 201)

    async def submit(self, count=1):
        status, tasks = await self.post("/tasks", {"tasks": [
            {"operation": "dummy", "payload": {"index": i}} for i in range(count)
        ]})
        self.assertEqual(status, 201)
        return tasks

    async def poll(self, worker):
        status, body = await self.post(f"/workers/{worker}/next-task")
        self.assertEqual(status, 200)
        return body["task"]

    async def update(self, task, action, worker="a", **extra):
        return await self.post(f"/tasks/{task['task_id']}/{action}", {"worker_id": worker, **extra})

    async def test_pending_batch_unique_ids_and_get(self):
        tasks = await self.submit(3)
        self.assertEqual(len({task["task_id"] for task in tasks}), 3)
        for task in tasks:
            self.assertEqual(task["status"], "pending")
            self.assertEqual(task["attempt_count"], 0)
            self.assertIsNone(task["assigned_worker"])
            self.assertIsNone(task["started_at"])
            self.assertIsNone(task["assigned_at"])
            self.assertIsNotNone(datetime.fromisoformat(task["created_at"]).tzinfo)
            self.assertEqual(await self.request("GET", f"/tasks/{task['task_id']}"), (200, task))
        self.assertEqual(await self.request("GET", "/tasks"), (200, tasks))

    async def test_batch_validation_is_atomic(self):
        invalid = [{"tasks": []}, {"tasks": [{"operation": "image"}]},
                   {"tasks": [{"operation": "dummy"}, {"operation": "invalid"}]},
                   {"tasks": [{"operation": "dummy", "payload": []}]},
                   {"tasks": [{"operation": "dummy", "status": "completed"}]},
                   {"tasks": [{"operation": "dummy"}] * 1001}]
        for body in invalid:
            with self.subTest(body=str(body)[:120]):
                self.assertEqual((await self.post("/tasks", body))[0], 422)
        self.assertEqual(await self.request("GET", "/tasks"), (200, []))

    async def test_round_robin_uses_registration_order_and_skips_busy_workers(self):
        await self.add_workers("a", "b", "c")
        tasks = await self.submit(5)
        self.assertEqual([t["assigned_worker"] for t in tasks], ["a", "b", "c", None, None])
        self.assertEqual([t["status"] for t in tasks], ["assigned"] * 3 + ["pending"] * 2)
        first = await self.poll("a")
        await self.update(first, "start")
        await self.update(first, "complete")
        fourth = await self.poll("a")
        self.assertEqual(fourth["task_id"], tasks[3]["task_id"])
        self.assertEqual(fourth["attempt_count"], 1)

    async def test_round_robin_cursor_continues_across_batches(self):
        await self.add_workers("a", "b", "c")
        for expected in ["a", "b", "c", "a"]:
            task = (await self.submit())[0]
            self.assertEqual(task["assigned_worker"], expected)
            await self.poll(expected)
            await self.update(task, "start", expected)
            await self.update(task, "complete", expected)

    async def test_registration_distributes_already_pending_tasks(self):
        task = (await self.submit())[0]
        await self.add_workers("a")
        delivered = await self.poll("a")
        self.assertEqual(delivered["task_id"], task["task_id"])
        self.assertEqual(delivered["status"], "assigned")

    async def test_empty_poll_unknown_worker_and_unknown_task(self):
        await self.add_workers("a")
        self.assertIsNone(await self.poll("a"))
        self.assertEqual((await self.post("/workers/unknown/next-task"))[0], 404)
        self.assertEqual((await self.request("GET", "/tasks/unknown"))[0], 404)
        self.assertEqual((await self.post("/tasks/unknown/start", {"worker_id": "a"}))[0], 404)

    async def test_completed_lifecycle_timestamps_and_attempt_count(self):
        await self.add_workers("a")
        task = (await self.submit())[0]
        await self.poll("a")
        status, running = await self.update(task, "start")
        self.assertEqual(status, 200)
        self.assertEqual(running["status"], "running")
        self.assertIsNone(await self.poll("a"))
        status, completed = await self.update(task, "complete")
        self.assertEqual((status, completed["status"]), (200, "completed"))
        self.assertEqual(completed["attempt_count"], 1)
        times = [datetime.fromisoformat(completed[k]) for k in
                 ["created_at", "assigned_at", "started_at", "completed_at", "updated_at"]]
        self.assertEqual(times, sorted(times))
        self.assertIsNone(completed["failed_at"])

    async def test_invalid_transitions_and_wrong_owner_do_not_mutate_task(self):
        await self.add_workers("a", "b")
        task = (await self.submit())[0]
        for action in ["start", "complete", "fail"]:
            extra = {"error": "test"} if action == "fail" else {}
            self.assertEqual((await self.update(task, action, **extra))[0], 409)
        await self.poll("a")
        self.assertEqual((await self.update(task, "start", "b"))[0], 409)
        self.assertEqual((await self.update(task, "start", "unknown"))[0], 404)
        self.assertEqual((await self.update(task, "start"))[0], 200)
        self.assertEqual((await self.update(task, "start"))[0], 409)
        self.assertEqual((await self.update(task, "complete", "b"))[0], 409)
        completed = (await self.update(task, "complete"))[1]
        self.assertEqual((await self.update(task, "start"))[0], 409)
        self.assertEqual((await self.update(task, "fail", error="late"))[0], 409)
        self.assertEqual(await self.request("GET", f"/tasks/{task['task_id']}"), (200, completed))

    async def test_failure_is_terminal_and_releases_worker(self):
        await self.add_workers("a")
        tasks = await self.submit(2)
        await self.poll("a")
        await self.update(tasks[0], "start")
        self.assertEqual((await self.update(tasks[0], "fail", error=" "))[0], 422)
        status, failed = await self.update(tasks[0], "fail", error="simulated")
        self.assertEqual((status, failed["status"], failed["error"]), (200, "failed", "simulated"))
        self.assertIsNotNone(failed["failed_at"])
        self.assertIsNone(failed["completed_at"])
        self.assertEqual((await self.update(tasks[0], "complete"))[0], 409)
        self.assertEqual((await self.update(tasks[0], "fail", error="again"))[0], 409)
        self.assertEqual((await self.poll("a"))["task_id"], tasks[1]["task_id"])

    async def test_pending_cannot_start_and_updates_require_identity(self):
        task = (await self.submit())[0]
        self.assertEqual((await self.update(task, "start", "unknown"))[0], 404)
        await self.add_workers("a")
        self.assertEqual((await self.post(f"/tasks/{task['task_id']}/start"))[0], 422)

    async def test_concurrent_polls_deliver_once_and_never_to_wrong_worker(self):
        await self.add_workers("a", "b")
        task = (await self.submit())[0]
        results = await asyncio.gather(*(self.poll(name) for name in ["a", "b"] * 20))
        delivered = [item for item in results if item is not None]
        self.assertEqual([t["task_id"] for t in delivered], [task["task_id"]])
        self.assertEqual(delivered[0]["assigned_worker"], "a")

    async def test_threaded_polls_and_duplicate_completion_are_atomic(self):
        await self.add_workers("a")
        tasks = await self.submit(2)
        store = self.app.state.store
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: store.poll("a"), range(50)))
        self.assertEqual(sum(task is not None for task in results), 1)
        await self.update(tasks[0], "start")
        with ThreadPoolExecutor(max_workers=8) as pool:
            completions = list(pool.map(lambda _: store.update(tasks[0]["task_id"], "a", "complete"), range(50)))
        self.assertTrue(all(task.status == "completed" for task in completions))
        self.assertTrue(all(task.completed_at == completions[0].completed_at for task in completions))
        self.assertEqual((await self.poll("a"))["task_id"], tasks[1]["task_id"])
        self.assertEqual(store.get_task(tasks[1]["task_id"]).attempt_count, 1)

    async def test_openapi_documents_registration_conflict(self):
        _, schema = await self.request("GET", "/openapi.json")
        self.assertIn("409", schema["paths"]["/workers/register"]["post"]["responses"])

    async def test_registry_snapshots_and_new_app_are_independent(self):
        await self.add_workers("a")
        task = (await self.submit())[0]
        snapshot = self.app.state.store.get_task(task["task_id"])
        snapshot.payload["index"] = "changed"
        self.assertEqual(self.app.state.store.get_task(task["task_id"]).payload["index"], 0)
        self.app = create_app()
        self.assertEqual(await self.request("GET", "/tasks"), (200, []))


if __name__ == "__main__":
    unittest.main()
