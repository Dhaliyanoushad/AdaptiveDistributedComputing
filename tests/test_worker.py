"""Worker request contract and clean failure behavior; no network required."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests

spec = importlib.util.spec_from_file_location("registration_worker", Path(__file__).parents[1] / "worker" / "worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.stack.enter_context(patch.object(worker.socket, "gethostname", return_value="local-host"))
        self.stdout = self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = self.stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.post = self.stack.enter_context(patch.object(worker.requests, "post"))
        # Preserve the Phase 1 registration checks independently of the new loop.
        self.loop = self.stack.enter_context(patch.object(worker, "run_worker", return_value=0))

    def test_default_registration(self):
        self.post.return_value = Mock(status_code=201)
        self.assertEqual(worker.main(), 0)
        self.post.assert_called_once_with(
            "http://127.0.0.1:8000/workers/register",
            json={"worker_id": "local-host", "hostname": "local-host"},
            timeout=(3.05, 10), allow_redirects=False,
        )
        self.assertIn("Registration successful", self.stdout.getvalue())

    def test_environment_overrides(self):
        os.environ.update(MASTER_URL="http://192.168.1.10:8000/", WORKER_ID=" laptop-2 ")
        self.post.return_value = Mock(status_code=201)
        self.assertEqual(worker.main(), 0)
        self.assertEqual(self.post.call_args.args[0], "http://192.168.1.10:8000/workers/register")
        self.assertEqual(self.post.call_args.kwargs["json"]["worker_id"], "laptop-2")

    def test_http_errors_and_redirects_fail_without_retry(self):
        for status in [301, 409, 422, 500]:
            with self.subTest(status=status):
                self.post.reset_mock()
                self.post.return_value = Mock(status_code=status, text="registration rejected")
                self.assertEqual(worker.main(), 1)
                self.post.assert_called_once()
                self.assertIn(f"HTTP {status}", self.stderr.getvalue())

    def test_connection_and_timeout_failures(self):
        for error in [requests.ConnectionError("unreachable"), requests.Timeout("timed out")]:
            with self.subTest(error=error):
                self.post.side_effect = error
                self.assertEqual(worker.main(), 1)
        self.assertIn("ConnectionError", self.stderr.getvalue())
        self.assertIn("Timeout", self.stderr.getvalue())

    def test_invalid_configuration_does_not_send_request(self):
        for value in ["", "ftp://host", "http://", "http://host?query=yes"]:
            with self.subTest(url=value):
                os.environ["MASTER_URL"] = value
                self.assertEqual(worker.main(), 1)
        os.environ["MASTER_URL"] = "http://127.0.0.1:8000"
        os.environ["WORKER_ID"] = "   "
        self.assertEqual(worker.main(), 1)
        self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
