# Phase 1: basic Master–Worker communication

## API contract

| Endpoint | Result |
| --- | --- |
| `GET /health` | HTTP 200, `{"status":"ok"}` |
| `POST /workers/register` | HTTP 201 and the accepted worker record |
| `GET /workers` | HTTP 200 and an array of worker records, initially `[]` |
| `GET /docs` | Swagger UI |

Example registration JSON:

```json
{"worker_id": "laptop-2", "hostname": "my-laptop"}
```

Both fields are required strings. Surrounding whitespace is removed. Empty/whitespace-only strings, wrong types, missing fields, extra fields and malformed JSON return HTTP 422. Maximum lengths are 128 characters for worker IDs and 253 for hostnames. IDs are case-sensitive. Duplicate IDs return HTTP 409 with `{"detail":"Worker ID already registered"}`; the existing record is preserved. The master logs successful registrations.

The registry is a dictionary local to one master process. Restarting clears it. Do not use multiple server processes for this phase. No WebSockets, task execution, liveness detection, persistence or authentication is implemented.

## Later test: second laptop on the same Wi-Fi

This test has **not** been performed. Use a trusted private network.

1. On the master laptop, run `ipconfig` in CMD and find the active Wi-Fi adapter's IPv4 address (for example `192.168.1.10`).
2. Stop any local test master with Ctrl+C. From the project root, start it with an explicit LAN binding:

   ```bat
   master\.venv\Scripts\python.exe -m uvicorn master.main:app --host 0.0.0.0 --port 8000
   ```

3. If Windows Firewall prompts, allow this Python server on the trusted Private network only. No firewall settings were changed by project setup. If connections time out, check the network profile, firewall permission and router client/guest isolation. Avoid exposing this unauthenticated prototype to the internet.
4. On laptop 2, copy or clone the project source. Do not copy the virtual environments; create a local worker environment with Python 3.13.2. In CMD, change to that laptop's project directory and run:

   ```bat
   python -m venv worker\.venv
   worker\.venv\Scripts\python.exe -m pip install -r worker\requirements.txt
   set "MASTER_URL=http://192.168.1.10:8000"
   set "WORKER_ID=laptop-2"
   worker\.venv\Scripts\python.exe worker\worker.py
   echo %ERRORLEVEL%
   ```

   Replace the example IP with the master laptop's actual address. `0.0.0.0` is a bind address, not the worker's destination. `127.0.0.1` on laptop 2 refers to laptop 2 itself.

5. From laptop 2, open `http://192.168.1.10:8000/workers` or run `curl.exe http://192.168.1.10:8000/workers`. Confirm the `laptop-2` record and detected hostname. `/docs` is available at the same host and port. A duplicate attempt should report HTTP 409 and exit 1.
6. Stop the master with Ctrl+C when finished. Future local runs should use the default `127.0.0.1` binding again.

## Verification performed during implementation

- Master environment: Python `unittest` discovery ran **10 tests**, all passed. These cover health, empty/listed registries, registration/logging, duplicate preservation, multiple workers, invalid payloads, malformed JSON, whitespace normalization, isolated app instances and OpenAPI routes.
- Worker environment: Python `unittest` discovery ran **5 tests**, all passed. These cover defaults/request timeout, environment overrides, HTTP rejection/redirects, connection/timeout exceptions and invalid configuration.
- A real single-laptop localhost test started Uvicorn at `127.0.0.1:8000`, ran the worker with ID `phase1-local-check`, observed HTTP 201 and its success message, and confirmed that `/workers` contained the record. `/health` returned HTTP 200 with the expected status and `/docs` returned HTTP 200. The test server was then stopped with Ctrl+C.
- No real two-laptop test, browser interaction, image processing or frontend test was performed.

Run the two test commands in the README using their respective existing environments. Runtime requirements are unchanged by Phase 1.
