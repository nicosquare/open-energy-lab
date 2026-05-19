# Battery Load PV MVP Migration Note

This note records the selected legacy evidence and intended migration boundary
for the deterministic battery + load + weather + PV simulator MVP under
`src/open_energy_lab/simulator`.

## Target

- Target module path: `src/open_energy_lab/simulator`
- Initial validation paths:
  - `tests/unit/simulator/`
  - `tests/integration/simulator/`
  - `tests/fixtures/simulator/battery_load_pv_case.json`

## Exact Legacy Reference Files

- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/scripts/test_battery_consistency.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`
- `legacy/old_tpm/src_py/simulator/common/specs.py`
- `legacy/fed_trpo/src/custom/building.py`

## Intended Preserved Scope

- battery capacity, power-limit, efficiency, and SOC-bound semantics already
  established by the battery arbitrage MVP
- timestep-in-hours treatment and step-aligned pricing semantics
- discounted export settlement relative to import prices
- deterministic validation with absolute tolerance `1e-6` unless a stricter
  case is explicitly documented
- one signed net-grid value per step rather than simultaneous import and export
- selective PV metadata direction and one-net electricity-accounting evidence
  from the cited legacy references

## Intended Improved Scope

- explicit typed simulator components for load, weather, PV, and net-grid
  accounting instead of hiding them in broader building abstractions
- a documented deterministic weather-to-PV derivation inside simulator core
- human-readable weather field names with explicit mappings to canonical TMY
  source labels for the included MVP subset
- small committed synthetic fixtures with provenance notes and exact legacy
  evidence lists
- a clean explicit-dispatch boundary that remains compatible with future
  external controllers while preserving a built-in deterministic rule baseline

## Intended Rejected Scope

- wholesale copying of legacy simulator or building modules
- mandatory CityLearn, TorchRL, PyTorch, solver, notebook, W&B, GPU/SLURM, or
  Rust dependencies in simulator-core imports
- real weather downloads, real tariff ingestion, or external API adapters in
  the MVP
- broad weather-subsystem migration unrelated to the PV derivation path
- feeder/network physics, outage logic, or multi-building composition in the
  MVP

## Initial Fixture Direction

`tests/fixtures/simulator/battery_load_pv_case.json` starts as a structural
shell in Phase 1 and will be finalized later with deterministic numeric values
and invariant-backed expectations for:

- one explicit-dispatch execution path
- one built-in `price_threshold` execution path
- weather inputs using human-readable field names plus TMY label mappings
- derived PV output
- net-grid trace and settlement expectations

## Explicit Non-Goals

This feature does not add:

- planning or MPC implementations
- RL training loops or federated workflows
- CityLearn runtime integration
- solver-backed optimization
- notebook-first workflows
- W&B integrations
- GPU or SLURM execution paths
- Rust bindings
