# Simulator Fixtures

Fixtures in this directory support deterministic simulator validation for the
battery arbitrage MVP.

The first committed fixture is expected to be
`tests/fixtures/simulator/battery_arbitrage_case.json`, a small synthetic case
used by unit and integration tests for scenario assembly, battery trace
evaluation, and discounted export settlement.

Each committed simulator fixture must include:

- origin and author/source note
- legacy reference paths used as evidence
- generation command or manual construction note
- any seed used
- expected invariants or outputs
- numeric tolerance
- refresh policy

## Current Fixture

`tests/fixtures/simulator/battery_arbitrage_case.json` is the first active
simulator fixture.

- source: manually authored from the simulator contracts, then verified against
  the current implementation with `uv run python -c` trace calculations
- author: OpenAI Codex
- seed: none
- why it is committed: it is small, reviewable, deterministic, and exercises
  both explicit dispatch and built-in `price_threshold` execution paths
- exact legacy evidence:
  - `legacy/old_tpm/scripts/test_battery_consistency.py`
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
- expected invariants:
  - SOC stays within `[0.0, 1.0]`
  - realized power respects the configured limits
  - total settlement equals the sum of the step settlement values
  - export settlement uses the discounted export-price ratio
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented timestep, battery, policy, or
  discounted-settlement semantics intentionally change
