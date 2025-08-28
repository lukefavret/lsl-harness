---
title: <% tp.file.title %>
status: "💡 Idea"
project_type: "🌱 Personal/Speculative"
mode: "Standard"
design_type: "within-system, randomized, counterbalanced, repeated measures"
date_created: <% tp.date.now("YYYY-MM-DD") %>
last_updated: <% tp.date.now("YYYY-MM-DD") %>
case_version: "0.1-predev"
repo_tag: "v0.0.1-predev"
aliases: ["LSL Performance Harness","Lab Streaming Layer Benchmarks"]
cover_image: "![[path/to/cover.png]]"

# Ownership & compliance
owner: "Luke Favret"
license: "CC BY-4.0"
accessibility: "WCAG 2.2 AA"
irb_consent: "N/A"
confidentiality: "public"

# Registration / reproducibility
preregistered: false
prereg_link: ""

# Queryable skills (optional)
tags: [arc3, case-study, LSL, benchmarking, neurotech, BCI, timing, jitter, latency]
skills_cs: ["Python","C++","Docker","Linux","CI/CD","Data Viz","Testing"]
skills_psych: ["Signal Processing (basic)"]
skills_design: ["Prototyping","Benchmarking","Experiment Design"]
programs_target: ["CMU MHCI","UW HCDE"]
---

# ARC³ Case Framework — Release Template

> **Mode badge:** `Mode: Standard`  
> **Selection rule:** Using quant targets with ablations; evidence to be gathered in v0.1 baseline.

[!info] **Framework guardrails**
- **A.4 → C.1 contract:** every criterion defined in **A.4** appears as a row in **C.1**.
- **Status vocabulary:** `Pass | Partial | Fail` (to be set after baseline).
- **Reliability targets:** run-to-run variance target ≤ **10%** relative for all core metrics.
- **Conventions:** SI units; ISO-8601 dates; data sources as `system_log:<table>/<field>` or `instrument:<tool>@<version>`.

---

# ⭐ STAR Summary Card (Dual-Lane) — one screen

[!abstract] **One-liner** — A reproducible performance harness for LabStreamingLayer (LSL) that measures **latency, jitter, clock offset/drift, packet loss, and throughput** across configurations, for **BCI/neurotech engineers & researchers** evaluating pipeline reliability.

- **Role:** Solo (design, implementation, analysis) • **Duration:** pre-dev 1 week → baseline 1 week • **Tools:** Python/pylsl, C++ LSL, Docker, Linux perf/psutil, pandas, matplotlib, pytest, GitHub Actions • **Team:** 1 (Luke)

**S — Situation** — LSL is common in BCI pipelines, but benchmark results are anecdotal and non-comparable. Hiring and research decisions need **reproducible, configuration-aware** timing data.

**T — Target (from A.4)** — OWNER: Luke for all; DATA SOURCES: harness logs + LSL versions.
- T1 Latency p50/p99 under EEG-like loads within set bounds; loss = 0.  
- T2 Jitter (CV) ≤ 10% of sample period under baseline.  
- T3 Clock offset ≤ 2 ms median; drift ≤ 1 ms / 10 min after correction.  
- T4 Throughput fidelity ≥ 99.9% expected samples; CPU ≤ 1 core, RAM ≤ 500 MiB (baseline).  
- T5 Reproducibility: ≤ 10% relative run-to-run variance; one-command re-runs; CI green.

**A — Approach** — Within-system benchmarking; randomized, counterbalanced config order; N=3 runs per config (≥10 min each). Baselines vs stressed (CPU, scheduling) with **instrumented source & sink** and monotonic clocks. Version-pinned builds; Dockerized.

**R — Results (dual-lane)**  
- **Impact (industry):** A standard harness lowers integration risk, clarifies capacity planning, and surfaces safe operational envelopes.  
- **Evidence (academic):** (Pre-dev) Planned effect sizes: Δp99 latency vs baseline; Δloss under stress; sensitivity to buffer sizes & timestamp policy.

**Decision:** **TBD** (see **C.3** triggers for GO/PIVOT/KILL).

---

# Executive Summary (150–300 words)

This project delivers a **repeatable, configuration-aware benchmark** for LabStreamingLayer (LSL), focusing on five core metrics: end-to-end latency (p50/p99), inter-arrival jitter, clock offset/drift after LSL correction, packet loss, and throughput fidelity under EEG-like loads. Today, LSL performance claims are scattered and non-comparable across machines and operating conditions. That creates hidden risk for BCI and HCI systems where timing determines usability and validity.

The harness adopts a **within-system, randomized, counterbalanced** design to reduce order effects, with **N=3** 10-minute runs per configuration, capturing stable distributions and run-to-run variance. We define explicit **success thresholds** that are stringent enough to be decision-useful yet realistic for general-purpose OS scheduling: p50 ≤ 20 ms and p99 ≤ 50 ms latency with zero loss for **EEG-32@256 Hz** on localhost; jitter coefficient of variation ≤ 10% of the sample period; clock offset ≤ 2 ms and drift ≤ 1 ms/10 min; ≥ 99.9% sample fidelity; and ≤ 10% relative variance across re-runs. Stress ablations (CPU contention, buffer sizes, timestamp strategies) are part of the protocol to map safe envelopes, not just best-case numbers.

Artifacts are version-pinned and containerized, with **one-command** execution and CI checks, producing charts and a markdown report. If thresholds are met, we publish a **v0.1 baseline** and proceed to multi-host and device-in-the-loop variants; if not, we pivot or kill according to **C.3**. No human subjects are involved at this stage.

---

# A — Anchor & Aim

[!todo] **Section A: Action Plan**
- [x] Problem statement & provocation
- [ ] Add citations to LSL docs + prior benchmarking notes (after baseline)
- [x] Define audience, assumptions, constraints
- [x] Define **5** falsifiable hypotheses with success criteria + data sources

## A.1 Provocation & Problem
[!bug] **Core challenge** — BCI pipelines often rely on **unverified timing assumptions**. Without reproducible benchmarks, teams over- or under-engineer buffers and sync, degrading UX or validity.  
[!question] **“What-if?”** — What if we had a **standard, rerunnable harness** that reports defensible timing envelopes across common EEG-like loads and configurations?

## A.2 Prior Art & Theory
[!search] **To document post-baseline:** LSL reference docs; scattered community measurements; OS scheduling/timestamping literature relevant to user-space timing and monotonic clocks.

## A.3 Audience, Assumptions, Constraints
[!users] **Audience:** BCI/Neurotech engineers, HCI researchers, RA/Predoc mentors evaluating systems reliability.  
[!key] **Assumptions & constraints:** Single-host, localhost **baseline** on Linux; no human subjects; SI units; version-pinned builds; monotonic clocks; Dockerized runs. Multi-host and device-in-the-loop will be Phase 2.

## A.4 Hypotheses & Success Criteria (contract for C.1)
[!target] **Each hypothesis → 1 criterion with OWNER + DATA SOURCE. All appear in C.1.**

- **H1: Baseline latency & loss meet envelope for EEG-32@256Hz (localhost).**  
  - **Criterion:** Latency p50 ≤ **20 ms** and p99 ≤ **50 ms**; **0.0%** packet loss across **N=3** runs (10 min each).  
  - **Owner:** Luke  
  - **Data Source:** `system_log:latency.csv`, `system_log:loss.csv`; `instrument:LSL@<tag>`, `instrument:pylsl@<version>`

- **H2: Inter-arrival jitter is controlled (baseline).**  
  - **Criterion:** Jitter coefficient of variation (CV = σ/μ) ≤ **10%** of the sample period at sink for EEG-32@256Hz and EEG-128@1kHz profiles.  
  - **Owner:** Luke  
  - **Data Source:** `system_log:interarrival.csv`; `instrument:LSL@<tag>`

- **H3: Clock correction limits offset/drift.**  
  - **Criterion:** After LSL clock correction, **|median clock offset| ≤ 2 ms** and **|drift| ≤ 1 ms / 10 min** over 30-min sessions.  
  - **Owner:** Luke  
  - **Data Source:** `system_log:clock_offset.csv`; `instrument:LSL@<tag>`

- **H4: Throughput fidelity & resource budget.**  
  - **Criterion:** Delivered samples ≥ **99.9%** of expected; **CPU ≤ 1.0 core** avg and **RAM ≤ 500 MiB** avg (baseline).  
  - **Owner:** Luke  
  - **Data Source:** `system_log:counts.csv`, `system_log:resources.csv`; `instrument:psutil@<version>`

- **H5: Reproducibility & stress envelope.**  
  - **Criterion:** Run-to-run relative variance (per metric) ≤ **10%** (baseline). Under CPU contention (70–80% system load) **p99 ≤ 100 ms** and loss ≤ **0.5%** for EEG-32@256Hz.  
  - **Owner:** Luke  
  - **Data Source:** `system_log:summary.parquet`, `system_log:stress.csv`; `instrument:stress-ng@<version>`

---

# R — Research & Realization

[!todo] **Section R: Action Plan**
- [x] Methods (design) — below
- [ ] Key findings — populate post-baseline
- [x] System design + notable technical challenges
- [x] Planned iterations + ≥1 **kill** gate

## R.1 Methods & Findings
**Design:** Within-system, randomized, counterbalanced order of configurations. **N=3** runs/config, **≥10 min** each. Profiles:  
- **EEG-32@256Hz** (float32, 32 ch)  
- **EEG-128@1kHz** (float32, 128 ch)

**Metrics:** end-to-end latency, inter-arrival jitter, loss rate, clock offset/drift, throughput, CPU/RAM.  
**Analysis:** Distributions (p50/p95/p99), CV for jitter, drift slope, effect sizes for ablations (Δ vs baseline).  
**Findings:** _Pre-dev — to be filled after v0.1 baseline._

## R.2 System Design & Implementation
**Architecture:** Pluggable **Source** (synthetic generators) → LSL stream → **Sink** (reader/recorder) with **monotonic timestamps** at both ends; data emitted to CSV/Parquet + charts.  
**Instrumentation:** CLOCK_MONOTONIC(_RAW), high-res timers, pinned process priority option, resource probes (CPU/RAM), optional `stress-ng` to induce contention.  
**Challenges & choices:**  
- **Timestamp policy:** prefer source-side stamping; record sink receive time; compute Δ.  
- **Containerization:** Docker for env parity; bind host clock; disable NTP changes during runs.  
- **CI:** smoke test (≤60 s), static config check, lint, reproducible seed.

**DoD (v0.1):** one-command run; pinned versions; 3 configs; N=3 runs; auto-plots; markdown report with thresholds vs observe.

## R.3 Iterations & Decision Gates
- **Iter-0 (skeleton):** single profile, single run — verify logs & plots.  
- **Iter-1 (baseline):** full N=3, two profiles — produce v0.1 report.  
- **Iter-2 (ablations):** buffers, timestamp policy, CPU stress.  
- **Kill gate:** If baseline p99 latency **> 100 ms** on localhost **and** run-to-run variance **> 20%** after two iterations, **kill** current approach and reassess timestamping/buffering strategy.

---

# C — Characterization, Critique, & Continuation

[!todo] **Section C: Action Plan**
- [ ] Fill **C.1** after baseline (rows pre-declared)
- [x] Draft **C.2** validity checklist (pre-dev)
- [x] Draft **C.3** plan with dates/triggers/kill-criteria

## C.1 Characterization (Outcome vs Criteria)

### Standard / Lite (Quant/Hybrid)
| Criterion (A.4) | Target | Observed | N / CI or SE | Baseline/Control | Ablation / Note | Data Source | **Status** |
|---|---:|---:|---|---:|---|---|---|
| H1: Latency & loss (EEG-32@256Hz) | p50 ≤ 20 ms; p99 ≤ 50 ms; loss 0.0% | — | N=3 × 10 min | Localhost (no stress) | Buffers, sched prio | system_log:latency.csv / loss.csv; instrument:LSL | — |
| H2: Jitter control | CV ≤ 10% of period | — | N=3 × 10 min | Baseline | Buffers | system_log:interarrival.csv | — |
| H3: Clock offset/drift | |offset| ≤ 2 ms; drift ≤ 1 ms/10 min | — | 30-min sessions | Timestamp policy | system_log:clock_offset.csv | — |
| H4: Fidelity & resources | ≥ 99.9% samples; CPU ≤ 1 core; RAM ≤ 500 MiB | — | N=3 × 10 min | Baseline | Stress vs no-stress | system_log:counts.csv / resources.csv | — |
| H5: Reproducibility & stress | ≤ 10% rel variance; under stress p99 ≤ 100 ms; loss ≤ 0.5% | — | N=3 × 10 min | Stress-ng 70–80% | Sched class | system_log:summary.parquet / stress.csv | — |

> **Note:** Status fields intentionally unset pre-baseline. Replace `—` with `Pass | Partial | Fail` after v0.1.

**Observed behavior summary** — _to be written post-baseline; must tie directly to A.4._

## C.2 Critique (Limits & Validity)
[!warning] **Internal validity:** measurement overhead (reader loop), Python GIL; mitigate via C++ reader cross-check and timer overhead accounting.  
**External validity:** single host, single OS; Phase 2 adds Windows/macOS and multi-host.  
**Construct validity:** inter-arrival jitter as proxy for perceived smoothness may miss application-level buffering; include buffer sensitivity ablation.  
**Statistical validity:** N=3 per config gives coarse SE; offset by distributional reporting (p-quantiles) and effect sizes on ablations.  
**Reliability:** target ≤ 10% relative variance; report actuals; seed synthetic sources.  
**Instrumentation/drift:** pin versions; record build hash; lock NTP changes during runs.  
**Bias/Accessibility:** none apparent; ensure docs WCAG 2.2 AA; avoid color-only encodings in plots.  
**Failure modes:** clock skew under virtualization; noisy neighbors in shared hosts.

## C.3 Continuation (Decision & Plan)
- **Decision:** **TBD** (post v0.1 baseline).  
- **Plan (owners/dates, America/Denver):**  
  1. Baseline harness + Docker + CI smoke test — **Luke**, by **2025-09-01**  
  2. v0.1 baseline runs (two profiles, N=3) + plots — **Luke**, by **2025-09-04**  
  3. Ablations (buffers, timestamp policy, CPU stress) — **Luke**, by **2025-09-06**  
  4. ARC³ case v0.1 write-up + PDF export — **Luke**, by **2025-09-08**  
  5. Publish repo tag + site project page update — **Luke**, by **2025-09-09**
- **Triggers (GO/PIVOT/KILL):**  
  - **GO:** H1, H4, H5 all **Pass** at baseline; H2/H3 **Pass or Partial**.  
  - **PIVOT:** Any of H1/H4/H5 = **Partial**; attempt buffer/timestamp strategy change.  
  - **KILL:** Any of H1/H4/H5 = **Fail** after two ablation iterations.
- **Risks & mitigations:**  
  - OS scheduling variance → document kernel/version; test with sched prio flag.  
  - Timer precision limits → use CLOCK_MONOTONIC_RAW; quantify timer overhead.  
- **Ethics/Compliance:** No human data. If later using device streams, add consent/log retention note.

---

## Compliance & Reproducibility Footer
**Repo & Artifacts:** [Tagged Repo] • [Data Dictionary] • [Anonymized Sample] • **Build Hash:** [hash]  
**Compliance:** IRB/Consent: ${irb_consent} • **License:** ${license} • **Accessibility:** ${accessibility}  
**Preregistration:** ${preregistered}  
**Versioning:** Last updated: <% tp.date.now("YYYY-MM-DD") %> • Case v${case_version} • Repo tag: ${repo_tag}  
**Lite disclosure:** N/A (Standard mode)
