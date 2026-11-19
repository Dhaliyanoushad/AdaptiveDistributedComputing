# Manual test execution record — blank template

Copy this file per session into your own reviewed evidence location. This blank template is not test evidence. Do not include secrets/private images; replace tokens with REDACTED. Allowed outcomes: **Pass / Fail / Blocked / Not Tested**. Never treat an expected result or automated pass as a manual observation.

## Session

- Tester / teammate: __________
- Actual date/time/timezone: __________
- Git revision and uncommitted changes: __________
- Scenario: localhost / two-laptop LAN / benchmark (choose): __________
- Laptop A OS/hostname/IP/CPU/RAM/power profile: __________
- Laptop B OS/hostname/IP/CPU/RAM/power profile: __________
- Python / OpenCV / Node / npm / browser versions: __________
- Network/router/Wi-Fi band/traffic/VPN conditions: __________
- Master mode/weights/timeouts/retry budget: __________
- Frontend origin/API URL/CORS configuration (no credentials): __________
- Dataset provenance/seed/workload hash/operation/params: __________
- Automated verification log UUID reviewed (not a manual pass): __________

## Case (repeat for each ID from TESTING_GUIDE.md)

| Field | Actual record |
| --- | --- |
| Case ID / phase / objective | |
| Prerequisites and initial/reset state | |
| Exact commands/actions and inputs | |
| Expected status/body/state/output | |
| Actual status/body/state/output | |
| Outcome: Pass / Fail / Blocked / Not Tested | |
| Task/attempt/run IDs | |
| Evidence filenames/screenshots/log timestamps | |
| Defect ID/severity/reproduction steps | |
| Known limitation versus new defect | |
| Retest date/revision/actual result | |

## Session summary

| Pass | Fail | Blocked | Not Tested | Total |
| --- | --- | --- | --- | --- |
| | | | | |

Outstanding blockers/defects: __________

Next action/owner: __________

For benchmarks retain every measured/warmup/failed trial, metadata and raw reports. No invented time/speedup or discarded failures. Append actual accepted results and retest history to TEST_RESULTS.md with evidence links; preserve earlier results and unexecuted status elsewhere.
