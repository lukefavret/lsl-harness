Goal: Identify improvements for clarity and maintainability without changing behavior. Leave review comments only; no code commits.

## Scope

Review these files:
- src/lsl_harness/ring.py
- src/lsl_harness/measure.py
- src/lsl_harness/metrics.py
- src/lsl_harness/report.py
- src/lsl_harness/fixtures/synthetic_outlet.py

## What to do

- Leave GitHub review comments only (no pushes/commits).
- Tag each comment with one of: [clarity] [naming] [docs] [structure] [safety] [test-gap].
- Include:
  - a one-sentence rationale, and
  - a ≤10-line before/after suggestion.
- Always note units (ms, Hz, ms/min) and shapes (array dims) when relevant.
- Call out concurrency assumptions (threading, ring drops) and CLI UX messages.
- Do not change logic, function signatures, timing behavior, or blocking characteristics.
- Avoid suggestions that introduce per-sample pulls or other performance regressions.

## Heuristics (flag when true)

- Function length > 50 lines, or > 5 parameters → propose extraction.
- Nesting depth > 3 → propose guard clauses / early returns.
- Magic numbers (e.g., 1e-6, 60.0) → propose named constants with units.
- Missing/weak docstrings on public functions/classes → propose Google-style docstrings.
- Ambiguous names (e.g., data, recv) → propose clearer names (e.g., recv_chunk_time_s).
- Unclear error messages → propose actionable messages (what to try next).

## Acceptance

- Comments link to exact lines.
- No behavioral changes are suggested.
- At least one suggestion per file for naming, docs, and structure.
- A summary comment at the end includes a checklist of proposed changes.

## Comment templates (copy these)

Template: naming

    [naming] metrics.py:L42–L43
    Rationale: Name does not convey units; easy to misread.
    
    Before
      offset = (recv_arr - src_arr) * 1000.0
    
    After (suggestion)
      offset_ms = (recv_arr - src_arr) * 1000.0  # ms

Template: structure

    [structure] cli.py:L55–L92
    Rationale: Function mixes collection, CSV I/O, and summarization (>50 lines).
    
    Before (snippet)
      # collection loop ...
      with open(out/"latency.csv", "w") as f: ...
      with open(out/"times.csv", "w") as f: ...
      summary = compute_metrics(...)
    
    After (suggestion)
      _write_artifacts(out, lat_ms, src_times, recv_times)
      summary = compute_metrics(collected, nominal_rate, ring_drops=w.ring.drops)
    
    Note: Add helper _write_artifacts(...) (pure I/O, ≤20 lines).

Template: docs

    [docs] measure.py:L12 (class docstring)
    Rationale: Public class lacks threading/drop-policy notes; add Args/Returns/Raises.
    
    Suggested docstring (excerpt)
      """Background inlet worker that pulls chunked samples on a daemon thread.
      
      Threading:
        A daemon thread calls pull_chunk and enqueues into a lock-protected ring.
        Main thread should drain frequently to bound latency; drop-oldest favors latency.
      
      Raises:
        RuntimeError: If no LSL stream matches the selector.
      """

Template: safety

    [safety] fixtures/synthetic_outlet.py:L36
    Rationale: burst_loss_pct skips entire chunks; users might assume per-sample loss.
    
    Suggestion: Clarify in docstring: "Simulates dropping a chunk, not individual samples."

Template: test-gap

    [test-gap] metrics.py:L70–L83
    Rationale: Drift slope lacks explicit test for ±2.0 ms/min injection.
    
    Suggestion: Add unit test asserting slope within ±0.2 for synthetic 2.0 ms/min.

## Summary checklist (for the final review comment)

- [ ] Rename for unit clarity (*_ms, *_s, eff_hz)
- [ ] Extract helpers to reduce function length / nesting
- [ ] Replace magic numbers with named constants (include units)
- [ ] Add/strengthen docstrings (Args/Returns/Raises; units; shapes)
- [ ] Improve error messages with actionable guidance
- [ ] Note concurrency assumptions and ring drop policy
- [ ] Identify missing tests (drift, burst-loss, rate mismatch)

## Optional: enable docstring lint in Ruff (maintainers)

Add this to pyproject.toml to lint docstrings with Google style:

    [tool.ruff.lint]
    select = ["E","F","I","UP","B","D"]
    ignore = ["D203","D213","D401"]
    
    [tool.ruff.lint.pydocstyle]
    convention = "google"
