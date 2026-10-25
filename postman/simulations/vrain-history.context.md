# VRAIN history simulation

Created 2026-10-25 from the live-observed VRAIN response shape; synthetic values only.

## Purpose

The vrain member exercises the real adapter and ingestion service. See docs/vrain-history.md for the source contract gate and the mock handler for cases.

## Execution

Start: `postman simulation run postman/simulations/vrain-history.sim.yaml --port 4920 --output ndjson --no-history`.
From app/: `python -m thongsothuyvan.tests.vrain_http_probe`, then `python -m thongsothuyvan.tests.vrain_ingestion_probe`. The first is DB-free; the second creates only an in-memory schema. Stop the server with Ctrl+C.

## Assumptions

- Observed 2026-10-25: mock lookup required Postman login, so owner discovery was unavailable. The local mock is based on live response field names, not a confirmed interval contract; passing probes cannot establish rainfall semantics, timezone or provider query limits.
- Observed 2026-10-25: localhost route prefix must be `/vrain`; dropping it fails routing. Probes configure synthetic credentials explicitly and must not use real keys in simulation logs.

## Observations

<!-- begin:observations -->
- 2026-10-25: vrain served all modeled HTTP success/error/timeout paths; no other members exist. Adapter probe passed zero/schema, 500/429/401, timeout and refused-port checks. Ingestion probe passed idempotent sample/revision writes and preservation after 401.
<!-- end:observations -->

## What didn't work

- 2026-10-25: the initial DB-free probe raised `AppRegistryNotReady` because the adapter imported credentials through the legacy model-dependent service. Shared credentials were extracted to vrain_credentials.py; rerun passed.
