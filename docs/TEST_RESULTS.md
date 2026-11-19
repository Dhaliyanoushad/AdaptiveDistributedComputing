# Test results

## Actual automated rerun — 2026-11-19

Executed from the existing Windows repository using separate master and worker virtual environments. Both interpreters reported **Python 3.13.2**. These results describe this run only; no changes to application behavior or tests were made for this documentation task.

| Command | Passed | Failed | Errors | Skipped | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `master\.venv\Scripts\python.exe tests\run_master_tests.py` | 29 | 0 | 0 | 0 | Exit 0; `Ran 29 tests in 2.567s`, `OK` |
| `worker\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_worker*.py" -v` | 19 | 0 | 0 | 0 | Exit 0; `Ran 19 tests in 0.256s`, `OK` |
| **Total test methods** | **48** | **0** | **0** | **0** | Includes existing Phases 1-3 tests |

Additional checks actually executed:

- Each environment's `python --version`: Python 3.13.2.
- Each environment's `python -m pip check`: `No broken requirements found.` These are dependency consistency checks, not additional test methods.

## Scope and limitations

- The existing test-only master runner was used because earlier attempts in this session history found a Windows asyncio socketpair restriction. Standard master discovery was not rerun during this documentation task; no new result is claimed for that command.
- The master image round-trip method exercised all four operations through ASGI endpoints and a real processor subprocess in the worker environment. Multipart transfer, task state, output upload and completed image downloads were checked.
- No live Uvicorn/TCP integration, browser visual assessment, multi-device performance measurement or two-laptop LAN test was run during this rerun. Mocked worker requests do not establish real network connectivity.
- Earlier implementation runs are recorded in `phase1.md`, `phase2.md` and `phase3.md`; they are historical evidence, not additional passes counted here. Earlier failed installs/blocked runs remain documented in the environment reports.
- Unresolved verification gaps: live TCP image processing, visual quality across real photos, firewall/router behavior and different hardware. There were no automated test failures in this rerun.
- Existing product limits remain: in-memory metadata resets on restart, no worker reconnection/retries/redelivery, no heartbeat/recovery, no authentication, endpoint-level file limits after multipart parsing, and structural output validation rather than proof of correct work by an untrusted worker.

## Teammate manual testing — not performed yet

No teammate manual results have been supplied. All Pass/Fail cells in [TESTING_GUIDE.md](TESTING_GUIDE.md) are intentionally blank. Two-laptop LAN testing is **pending**, not passed. Development and automated verification do not replace teammate acceptance testing.

When manual testing occurs, append the actual date, tester, commit/revision, OS/Python versions, device details, case IDs, observed status/body, Pass/Fail outcome and evidence. Preserve failures and retest history. Do not prefill expected outcomes as observed results.
