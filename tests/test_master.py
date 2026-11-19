"""Exercise FastAPI's ASGI interface without an external HTTP test client."""

import json
import unittest

from master.main import create_app


class MasterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.app = create_app()

    async def request(self, method: str, path: str, body: bytes = b"") -> tuple[int, object]:
        messages = []
        delivered = False

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)

        await self.app(
            {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
             "query_string": b"", "root_path": "", "headers": [(b"content-type", b"application/json")],
             "client": ("127.0.0.1", 1234), "server": ("test", 80)},
            receive, send,
        )
        status = next(m["status"] for m in messages if m["type"] == "http.response.start")
        content = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        return status, json.loads(content)

    async def register(self, payload):
        return await self.request("POST", "/workers/register", json.dumps(payload).encode())

    async def worker_identities(self):
        status, records = await self.request("GET", "/workers")
        return status, [{key: record[key] for key in ("worker_id", "hostname")} for record in records]

    async def test_health(self):
        self.assertEqual(await self.request("GET", "/health"), (200, {"status": "ok"}))

    async def test_initial_registry_is_empty(self):
        self.assertEqual(await self.request("GET", "/workers"), (200, []))

    async def test_registration_listing_and_logging(self):
        worker = {"worker_id": "laptop-1", "hostname": "device-1"}
        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            self.assertEqual(await self.register(worker), (201, worker))
        self.assertIn("laptop-1", captured.output[0])
        self.assertEqual(await self.worker_identities(), (200, [worker]))

    async def test_duplicate_id_does_not_replace_original(self):
        original = {"worker_id": "same", "hostname": "original"}
        await self.register(original)
        status, body = await self.register({"worker_id": "same", "hostname": "replacement"})
        self.assertEqual(status, 409)
        self.assertEqual(body["detail"], "Worker ID already registered")
        self.assertEqual(await self.worker_identities(), (200, [original]))

    async def test_multiple_workers(self):
        workers = [{"worker_id": str(i), "hostname": "shared-host"} for i in range(2)]
        for worker in workers:
            self.assertEqual((await self.register(worker))[0], 201)
        self.assertEqual(await self.worker_identities(), (200, workers))

    async def test_validation_rejects_invalid_payloads_without_mutating_registry(self):
        valid = {"worker_id": "worker", "hostname": "host"}
        invalid = [{}, {"worker_id": "worker"}, {"hostname": "host"}, None, [],
                   {**valid, "unexpected": True}]
        for field, limit in [("worker_id", 128), ("hostname", 253)]:
            for value in ["", "   ", None, 123, True, [], "x" * (limit + 1)]:
                invalid.append({**valid, field: value})
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual((await self.register(payload))[0], 422)
        self.assertEqual(await self.request("GET", "/workers"), (200, []))

    async def test_malformed_json(self):
        self.assertEqual((await self.request("POST", "/workers/register", b"{"))[0], 422)

    async def test_whitespace_normalization_and_duplicate(self):
        self.assertEqual(await self.register({"worker_id": " worker ", "hostname": " host "}),
                         (201, {"worker_id": "worker", "hostname": "host"}))
        self.assertEqual((await self.register({"worker_id": "worker", "hostname": "other"}))[0], 409)

    async def test_app_instances_have_independent_registries(self):
        await self.register({"worker_id": "one", "hostname": "host"})
        self.app = create_app()
        self.assertEqual(await self.request("GET", "/workers"), (200, []))

    async def test_openapi_has_phase_one_endpoints(self):
        status, schema = await self.request("GET", "/openapi.json")
        self.assertEqual(status, 200)
        self.assertTrue({"/health", "/workers", "/workers/register"}.issubset(schema["paths"]))


if __name__ == "__main__":
    unittest.main()
