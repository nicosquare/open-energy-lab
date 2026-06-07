# Native Controller Pack Migration Note

Status: scaffold

This note reserves the migration record for spec `005-controller-pack`, which
introduces the first reusable native controllers under
`src/open_energy_lab/control`.

## Target Module Paths

- `src/open_energy_lab/control/__init__.py`
- `src/open_energy_lab/control/_config.py`
- `src/open_energy_lab/control/price_threshold.py`
- `src/open_energy_lab/control/soc_guardrail.py`
- `src/open_energy_lab/control/pv_self_consumption.py`

## Validation Paths

- `tests/unit/control/`
- `tests/integration/control/`
- `tests/integration/simulator/test_controller_fixture_schema.py`
- `tests/integration/simulator/test_controller_evaluation.py`
- `tests/integration/simulator/test_battery_arbitrage_trace.py`
- `tests/integration/simulator/test_battery_load_pv_trace.py`

## Legacy Source Paths

Preserved battery, timestep, and settlement evidence:

- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`

Current-step PV context evidence:

- `legacy/old_tpm/src_py/simulator/common/specs.py`
- `legacy/fed_trpo/src/custom/building.py`

Rejected integration-direction evidence:

- `legacy/fed_trpo/src/custom/citylearn.py`
- `legacy/fed_trpo/src/utils/cl_torchrl_helper.py`

## Planned Preserve / Improve / Reject Record

### Preserve

- Simulator-owned feasibility enforcement and settlement behavior.
- Deterministic controller evaluation through `open_energy_lab.simulator`.
- Import-light stable surfaces under `open_energy_lab.core` and
  `open_energy_lab.simulator`.

### Improve

- Add a reusable package-root controller surface in `open_energy_lab.control`.
- Add typed per-controller configuration validation.
- Add controller-specific deterministic fixture evidence and support-matrix
  documentation.

### Reject

- Runtime imports from `legacy/*`.
- CityLearn adapters, RL training loops, policy networks, replay buffers, and
  solver-backed planning in the stable control package.
- Heavy optional dependency requirements for ordinary controller imports.

## Planned Fixture Record

Phase 1 reserves the following controller-pack fixture paths for later
population:

- `tests/fixtures/simulator/price_threshold_controller_case.json`
- `tests/fixtures/simulator/soc_guardrail_arbitrage_case.json`
- `tests/fixtures/simulator/pv_self_consumption_case.json`

Later tasks must replace scaffold placeholders with verified deterministic
outputs, provenance details, and exact validation targets.

## Planned Documentation Follow-Up

- Promote the stable control package surface in `docs/migration/api-maturity.md`.
- Record dependency classification updates in
  `docs/migration/dependency-policy.md`.
- Record controller-pack validation shape in
  `docs/migration/parity-validation.md`.
