# SH daily experimental protocol v1 (before benchmark run)

Primary experiment: approved hydrology Qve target, production Qcm feature, six historical daily rain fields. Issue 07:30 D, target D+1 calendar day. Assume each completed observation day is available at 07:00 next day; this is hindcast only. Secondary lag=2 experiment is sensitivity, never selected by 2026 results.

Chronological train target 2023-2024; validation 2025; test 2026 through last available approved-target candidate. Purge labels not assumed known at the next fold's earliest issue. Candidate Ridge feature groups: qve/season, plus Qcm, plus rain, plus rain without ambiguous Xa_Ea_M_doan; alphas 0.1/1/10/100/1000. Select once by validation MAE. Compare final test only selected Ridge and B0/B1. Choose baseline by validation MAE, not test. Predictions clipped at zero identically for sklearn and portable inference.

Technical acceptance: causal lag/date and missing-data tests; train-only preprocessing; purged labels; unchanged raw DB; deterministic rebuild; portable coefficient artifact checksum/parity. Skill target: at least 10% test MAE gain vs preselected baseline, without claiming flood skill when no high-flow test events exist. Historical availability and rain zero/missing semantics remain unverified, so production approval is always false in v1.

Nested retrospective LOFEO: development data only, Q>300 candidate clusters with one observed low day bridged, missing days break clusters, nine-day purge on each side; tune within remaining fold only. Some training events may occur after held-out event, so this is NOT an operational forecast backtest. No 2026 labels are used to select a fold model. No tuning after inspecting 2026; subsequent model changes require a fresh final evaluation period.
