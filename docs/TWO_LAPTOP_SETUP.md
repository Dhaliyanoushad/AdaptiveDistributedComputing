# Two-laptop deployment and test preparation

**NOT YET EXECUTED as a real two-laptop test.** These commands are a handoff procedure, not evidence of a pass. Use a trusted Wi-Fi/LAN; no public port forwarding. Laptop A hosts master/frontend and optionally worker A. Laptop B adds worker B. Open CMD in the repository on each machine; paths are relative.

## 1. Prerequisites and source

On A: Python 3.13.2 baseline, Node >=22.14, npm, Git; run scripts/setup.cmd. On B only Python 3.13 is needed at runtime if source was copied; Git is useful for matching revision. Do not copy virtual environments or node_modules between machines. Record `git rev-parse HEAD`, OS, Python/OpenCV, physical device, RAM/CPU and network conditions in TEST_EXECUTION_TEMPLATE.md.

Worker-only installation on B:

```bat
python --version
if not exist worker\.venv\Scripts\python.exe python -m venv worker\.venv
worker\.venv\Scripts\python.exe -m pip install -r worker\requirements.txt
worker\.venv\Scripts\python.exe -m pip check
```

Use `ipconfig` on A. Find the active Wi-Fi/Ethernet IPv4, not a disconnected adapter, VPN address or 127.0.0.1. **192.168.1.10 below is only an example; replace it everywhere with A's actual address.** Addresses may change after reconnecting Wi-Fi.

## 2. Start A: master, worker A and frontend

Master terminal A1:

```bat
set "MASTER_HOST=0.0.0.0"
set "MASTER_PORT=8000"
set "SCHEDULER_MODE=static"
set "CORS_ALLOWED_ORIGINS=http://192.168.1.10:5173,http://127.0.0.1:5173,http://localhost:5173"
scripts\start_master.cmd
```

No reload/multiple master processes. Binding 0.0.0.0 permits LAN interfaces; it is not a URL destination. Worker A terminal A2:

```bat
set "MASTER_URL=http://127.0.0.1:8000"
set "WORKER_ID=laptop-a-1"
scripts\start_worker.cmd
```

Frontend terminal A3, if B will access the browser dashboard:

```bat
set "FRONTEND_HOST=0.0.0.0"
set "FRONTEND_PORT=5173"
set "VITE_MASTER_URL=http://192.168.1.10:8000"
scripts\start_frontend.cmd
```

On A open http://192.168.1.10:5173 or loopback:5173 if listed in CORS. On B open http://192.168.1.10:5173. Vite's API URL is public browser/build configuration, so it must be reachable from that browser. CORS entries must match the actual frontend scheme/host/port exactly, without trailing slash. WebSocket uses the same allowlist and derives ws/wss from VITE_MASTER_URL. HTTPS pages cannot use insecure HTTP/WS mixed content; the supplied LAN setup is plain HTTP on a trusted network, not internet deployment.

If the dashboard is used only on A, keep FRONTEND_HOST=127.0.0.1 and no inbound Node allowance is needed. Python master still needs LAN access for B's worker. Vite dev hosting is for evaluation, not a hardened production server; build artifacts alone do not provide a deployed HTTP service.

## 3. Start B and verify reachability

Before starting B's worker:

```bat
curl.exe -i http://192.168.1.10:8000/health
set "MASTER_URL=http://192.168.1.10:8000"
set "WORKER_ID=laptop-b-1"
set "HEARTBEAT_INTERVAL=3"
scripts\start_worker.cmd
```

Expected health 200/{status:ok}; worker registration succeeds and continues polling. In a separate B CMD:

```bat
curl.exe http://192.168.1.10:8000/workers
curl.exe http://192.168.1.10:8000/workers/laptop-b-1
```

Expected both distinct IDs, actual hostnames, online status, changing last_seen and CPU/RAM/available MiB (possibly null on collection error). Public records never include private session/attempt tokens. Reusing an online ID must fail 409. Offline reconnect rotates credentials; it does not resurrect old attempt ownership.

## 4. Images, heartbeat and recovery

Put real JPG/PNG test images on A only. Use dashboard Image processing or curl:

```bat
curl.exe -i -X POST http://192.168.1.10:8000/images/tasks -F "files=@test_images\one.jpg;type=image/jpeg" -F "files=@test_images\two.png;type=image/png" -F "operation=grayscale"
curl.exe http://192.168.1.10:8000/tasks
```

Expect one task per file, distribution across eligible workers and completed PNGs. No shared input/output path is required on B. Copy a completed ID and open `/tasks/ID/result` or download `/tasks/ID/result/download`. Repeat resize/blur/edges using API_REFERENCE.md parameters. Capture both worker consoles, real task history and output dimensions/visual evidence.

Stop B with Ctrl+C while it owns real image work; small images may finish too quickly, so do not record an interruption pass unless achieved. For deterministic slow recovery practice first use dummy tasks with TASK_DELAY=15 (not image benchmark evidence). Wait >10 seconds plus sweep interval, verify offline and a retry on A within MAX_TASK_ATTEMPTS. Restart B after offline; old sessions/generations must not publish stale work. Keep valid output hashes/evidence before/after rejection. Full private-header cases are in TESTING_GUIDE.md; never include real tokens in shared evidence.

## 5. Static/adaptive benchmark protocol

Use an isolated fresh master per mode, one identical workload and filled metadata with actual physical-device labels. Do not run dashboard uploads or unrelated jobs during timing. For the single-device run, start only laptop-a-1 with master static. For distributed runs start both workers and master static, then restart all for adaptive. CORS is not required by the CLI client, but the master must remain reachable.

```bat
scripts\benchmark_prepare.cmd --directory benchmarks\workloads\lan-small-42 --profile small --seed 42
copy benchmarks\environment.example.json benchmarks\environment-lan.json
```

Edit worker keys/hostnames/hardware/network metadata for laptop-a-1/laptop-b-1, replacing all placeholders. Same metadata file across modes:

```bat
worker\.venv\Scripts\python.exe -m benchmarks.runner --master-url http://192.168.1.10:8000 --mode single --workers laptop-a-1 --workload benchmarks\workloads\lan-small-42 --environment benchmarks\environment-lan.json --trials 3 --warmups 1
```

After appropriate master/worker restart, use --mode static/adaptive and --workers laptop-a-1,laptop-b-1. Generate a new report directory:

```bat
scripts\benchmark_report.cmd --source benchmarks\results --output benchmarks\reports\lan-experiment-01
```

Observe real CSV/JSON/SVG/Markdown results; failed/partial trials remain invalid. A loopback/multiple-process experiment is not a two-physical-laptop result. Do not claim speedup without valid measured comparisons. No actual benchmark was executed during implementation.

## 6. Ports, diagnosis and minimum allowances

Runtime inbound TCP on A: **8000** for Python master HTTP/WebSockets; **5173** for Node/Vite only if remote browsers need it. B's worker uses outgoing HTTP to A:8000 and needs no inbound worker port. Allow only these intended apps/ports on the trusted Windows Private profile. If an app prompt appears, review it and permit Private only if appropriate. Do not disable firewall, change antivirus policy or configure router forwarding automatically. Package installation separately needs HTTPS/DNS access.

Read-only checks from CMD (replace IP):

```bat
ipconfig
netstat -ano | findstr :8000
netstat -ano | findstr :5173
powershell -NoProfile -Command "Test-NetConnection 192.168.1.10 -Port 8000"
python scripts\diagnose_network.py
nslookup registry.npmjs.org
```

Check the owning PID before stopping only your own application; never kill unrelated processes. A listener on 127.0.0.1 is not reachable from B. Guest Wi-Fi/client isolation, mismatched subnets, VPNs, stale IPs and firewall profile can prevent access. A health pass does not prove browser CORS/WS permission: inspect F12 Network/WS and Console separately. Exact allowed origin and VITE_MASTER_URL matter. Never use 0.0.0.0 as MASTER_URL or 127.0.0.1 on B to reach A.

Implementation diagnostics in the restricted execution context found bind/listen success on ephemeral, 8000 and 5173 ports; ephemeral loopback connect failed WinError 10013; bounded socketpair child stalled; DNS lookup failed. No listeners were listed for application ports after those temporary probes. This rules against an application port conflict in that observation and points to context/security restrictions on socket operations, but does not identify an exact policy/vendor or prove a normal user CMD is unrestricted. Ask the machine administrator to review policy if the same failure occurs there. No security settings were changed.

Full npm audit currently has 1 moderate/2 critical development findings. Production-only audit reports zero. Compatible update attempts failed ENOTFOUND; do not force-upgrade blindly or label the issue fixed.

## Evidence and shutdown

Use TEST_EXECUTION_TEMPLATE.md: revision, dates, both machine specs/IPs, browser/OS/runtime versions, network conditions, exact commands, case IDs, actual responses, task/run IDs, screenshots and defect references. Mark Not Tested or Blocked honestly. No teammate/LAN pass has been supplied yet. Stop workers/frontend/master with Ctrl+C, restore loopback defaults for later local use and clear any local token variables. Master restart loses all metadata; disk images are not persistent task recovery.
