# Roadmap — LSL Performance Harness

## Milestones (America/Denver)

- **M1 — Baseline harness runnable** — *2025-09-01*
  - One-command run (`scripts/run_baseline.sh`)
  - Docker build + CI smoke passing
  - ✅ Acceptance: produces `reports/baseline-v0.1/summary.parquet` and figures

- **M2 — v0.1 Baseline results (2 profiles, N=3)** — *2025-09-04*
  - Profiles: EEG-32@256Hz, EEG-128@1kHz
  - ✅ Acceptance: p50/p99 latency, jitter CV, loss, offset/drift, resource charts committed

- **M3 — Ablations (buffers, timestamp policy, CPU stress)** — *2025-09-06*
  - `stress-ng` 70–80% load scenario
  - ✅ Acceptance: delta plots vs baseline + effect sizes

- **M4 — ARC³ case v0.1 + tagged release** — *2025-09-08*
  - `/docs/cases/lsl-harness-arc3-v0.1.md` complete
  - Tag `v0.1.0` + GitHub Release with report artifacts

## Decision Gates (from ARC³ C.3)

- **GO:** H1, H4, H5 = Pass at baseline; H2/H3 = Pass or Partial
- **PIVOT:** Any of H1/H4/H5 = Partial → try buffer/timestamp changes
- **KILL:** Any of H1/H4/H5 = Fail after two ablation iterations

## Risks & Mitigations

- OS scheduling variance → document kernel; optional sched prio flag
- Timer precision → use `CLOCK_MONOTONIC_RAW`; measure overhead

*(This roadmap is intentionally short; use Issues/Projects for task granularity.)*
