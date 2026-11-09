"""Polling and dummy execution tests without external HTTP requests."""

import unittest
from unittest.mock import Mock, patch

import test_worker

worker = test_worker.worker


class WorkerTaskTests(unittest.TestCase):
    def test_poll_execute_and_complete_with_timeouts(self):
        task = {"task_id": "task-1", "operation": "dummy", "payload": {}}
        replies = [Mock(status_code=200, json=Mock(return_value={"task": None})),
                   Mock(status_code=200, json=Mock(return_value={"task": task})),
                   Mock(status_code=200), Mock(status_code=200), KeyboardInterrupt()]
        with patch.object(worker.requests, "post", side_effect=replies) as post, \
                patch.object(worker.time, "sleep") as sleep:
            with self.assertRaises(KeyboardInterrupt):
                worker.run_worker("http://master", "worker-1", 1, 0.5)
        self.assertEqual(sleep.call_args_list[0].args, (1,))
        self.assertEqual(sleep.call_args_list[1].args, (0.5,))
        self.assertTrue(post.call_args_list[2].args[0].endswith("/task-1/start"))
        self.assertTrue(post.call_args_list[3].args[0].endswith("/task-1/complete"))
        for call in post.call_args_list:
            self.assertEqual(call.kwargs["timeout"], (3.05, 10))
            self.assertFalse(call.kwargs["allow_redirects"])

    def test_simulated_failure_reports_fail(self):
        task = {"task_id": "task-1", "operation": "dummy", "payload": {"fail": True}}
        replies = [Mock(status_code=200, json=Mock(return_value={"task": task})),
                   Mock(status_code=200), Mock(status_code=200), KeyboardInterrupt()]
        with patch.object(worker.requests, "post", side_effect=replies) as post, \
                patch.object(worker.time, "sleep"):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_worker("http://master", "worker-1", 1, 0)
        self.assertTrue(post.call_args_list[2].args[0].endswith("/fail"))
        self.assertIn("error", post.call_args_list[2].kwargs["json"])

    def test_start_rejection_prevents_completion(self):
        task = {"task_id": "task-1", "operation": "dummy", "payload": {}}
        with patch.object(worker.requests, "post", side_effect=[
            Mock(status_code=200, json=Mock(return_value={"task": task})),
            Mock(status_code=409, text="invalid state"),
        ]) as post:
            with self.assertRaisesRegex(ValueError, "HTTP 409"):
                worker.run_worker("http://master", "worker-1", 1, 0)
            self.assertEqual(post.call_count, 2)


class WorkerLoopExitTests(unittest.TestCase):
    setUp = test_worker.WorkerTests.setUp

    def test_keyboard_interrupt_exits_cleanly(self):
        self.post.return_value = Mock(status_code=201)
        self.loop.side_effect = KeyboardInterrupt()
        self.assertEqual(worker.main(), 0)

    def test_polling_failure_exits_nonzero_without_reregistering(self):
        self.post.return_value = Mock(status_code=201)
        self.loop.side_effect = ValueError("HTTP 404")
        self.assertEqual(worker.main(), 1)
        self.post.assert_called_once()

    def test_invalid_delays_rejected_before_registration(self):
        for key, values in {"POLL_INTERVAL": ["0", "-1", "nan", "inf", "bad"],
                            "TASK_DELAY": ["-1", "nan", "inf", "bad"]}.items():
            for value in values:
                with self.subTest(key=key, value=value), patch.dict(worker.os.environ, {key: value}):
                    self.assertEqual(worker.main(), 1)
        self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
