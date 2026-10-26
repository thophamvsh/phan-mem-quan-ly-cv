# Sông Hinh daily Qvề experimental pipeline

**v1 is NOT qualified for production.** Ridge did not beat the baseline on the fixed 2026 holdout. See `E:/SangKien/DubaoQveSH.ketqua-v1.md`. No schedule, model API, database model migration or live forecast was enabled.

## What is implemented

- Read-only PostgreSQL source export: approved-target candidates from `ThongSoThuyVanThucTe.qve`, Qcm from production `cot_j`, six daily rain fields. No Google/VRAIN requests during training.
- Pure Python causal feature builder. Issue 07:30 D, target D+1; assumed availability at observation day + lag, 07:00. This is retrospective hindcast, not reconstructed actual approval history.
- B0/B1 and 20 Ridge candidates selected only on validation 2025, training labels purged against next fold issue time. Fixed 2026 results are already exposed and must not be reused for new final model selection.
- Chronological reports, nested retrospective LOFEO, lag=2 sensitivity, CSV/manifest/checksums, portable JSON coefficients with exact preprocessing, and default baseline fallback for the unqualified candidate.
- Missing days are calendar gaps, missing sums stay missing with coverage indicators. Duplicate daily records are excluded. Historical unknown rain zeros remain an explicit limitation, not verified observations.

## Reproduce locally

Training dependencies are separate from backend runtime; do not install research requirements in the Orange Pi app image by default.

```powershell
python -m venv .venv-inflow
.venv-inflow/Scripts/python -m pip install -r research/inflow_sh/requirements.txt
# Start local database if needed; do not start collection workers for an export.
docker compose start db
# Create research/inflow_sh/runs first, then export to a temporary container file:
docker compose run --name sh-export --no-deps -T -e REALTIME_SNAPSHOT_SCHEDULER_ENABLED=false app python manage.py export_inflow_sh --output /tmp/sh-source.json
docker cp sh-export:/tmp/sh-source.json research/inflow_sh/runs/source-v1.json
docker rm sh-export
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.venv-inflow/Scripts/python research/inflow_sh/train.py --source research/inflow_sh/runs/source-v1.json --output research/inflow_sh/runs/new-primary --lag-days 1 --event-checks
.venv-inflow/Scripts/python research/inflow_sh/train.py --source research/inflow_sh/runs/source-v1.json --output research/inflow_sh/runs/new-sensitivity --lag-days 2
```

Output directories must be new: the trainer refuses overwrite. Source and business-data outputs under runs/ are ignored by Git. Export refuses overwriting an existing file. The immutable source hash is recorded. Never commit credentials, source JSON, CSV datasets or model business reports accidentally.

Current frozen primary run is `runs/v1-lag1-verified` (technical reproducibility verified, NOT data/production qualification). `runs/v1-lag1` is the initial numerical run; CSV data and test predictions are byte-identical on rebuild. Secondary sensitivity is `runs/v1-lag2`.

## Dependency-free inference check

```powershell
python research/inflow_sh/predict.py --source research/inflow_sh/runs/source-v1.json --model research/inflow_sh/runs/v1-lag1-verified/model.json --issue-time 2026-10-26T07:30:00+07:00
```

Default returns `experimental_baseline_only`, using B0 chosen on 2025, NOT B1 chosen after looking at 2026. Stale data returns unavailable. Research-only `--allow-unqualified-ridge` exposes Ridge predictions for diagnosis, never an approved operational output. Training lag and artifact lag must match; historical issues earlier than the final model fit cutoff are rejected. The CLI does not prove inputs were truly known at the hypothetical historical issue time.

## Checks

```powershell
.venv-inflow/Scripts/python -c "import sys,unittest;sys.path.insert(0,'app');suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromName('thongsothuyvan.tests.test_inflow_forecasting'),unittest.defaultTestLoader.loadTestsFromName('research.inflow_sh.test_training')]);raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())"
```

Includes future-input invariance, target/source correctness, missing calendar days, duplicate dates, delayed availability, stale rejection, artifact checksum/schema, preprocessing train-only, portable/sklearn parity and label purge. No ARM performance claim: benchmark on the actual Orange Pi remains required before deployment.

## Prospective B0 shadow tracking

Implemented separately in backend migration 0025, with automatic schedule OFF by default. See [docs/inflow-b0-shadow.md](../../docs/inflow-b0-shadow.md) from the repository root (path: docs/inflow-b0-shadow.md). Commands: publish_inflow_b0_sh (--dry-run optional), reconcile_inflow_b0_sh, report_inflow_b0_sh. These read the current hydrology source directly, do not rely on the historical source JSON and cannot backdate forecasts. One real local future-target forecast was published for testing; no target has yet ended or been scored. This does not qualify Ridge v1 or enable operational control.
