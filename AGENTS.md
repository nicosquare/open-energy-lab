<!-- SPECKIT START -->
Current Spec Kit plan: `specs/013-reference-robust-fcr-bidding/plan.md`

For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan.
<!-- SPECKIT END -->

# Repository Working Rules

Open Energy Lab is being shaped into a unified research library. The current
`legacy/*` submodules are reference material from previous projects, not the
target architecture.

## Boundaries

- `.specify/` and `.agents/` are Spec Kit workflow/configuration areas.
- `legacy/old_tpm` is a reference for Rust/Python simulation, SPN/MIO, weather,
  and experiment behavior.
- `legacy/fed_trpo` is a reference for federated RL, PPO/TRPO, CityLearn,
  sweep configs, and SLURM/W&B workflows.
- New reusable library code belongs under `src/open_energy_lab`, with tests
  under `tests`.
- New reusable library code must not be added to `legacy/*` unless a spec
  explicitly authorizes a migration or legacy-maintenance change.

## Migration Rules

- Cite exact legacy source paths when migrating behavior.
- Prefer extracting tested behavior over copying files wholesale.
- Preserve only behavior that has tests, fixtures, deterministic configs, or
  documented equations to validate it.
- Treat heavyweight dependencies as optional or isolated unless the active spec
  explicitly makes them core dependencies.
- Keep simulator, TPM, RL, optimization, weather, planning, control, notebook,
  W&B, GPU/SLURM, and Rust behavior migrations out of foundation-only work.

## Current Weather Feature Guidance

- For `007-stochastic-weather`, keep default validation offline and
  fixture-backed. Do not make live PVGIS fetches part of the routine review
  path.
- Preserve the explicit boundary between artifact-preserved canonical weather
  fields and the narrower weather fields currently consumed by the simulator
  PV path.
- Keep blackout behavior simulator-side. Do not couple outage semantics to
  weather fitting or sampling.
- If optional live-fetch checks or optional dependencies are unavailable,
  document that in the feature quickstart or final response instead of
  widening the base environment requirements.

## Current Demand Feature Guidance

- For `008-weather-demand-modeling`, keep default validation offline and
  fixture-backed. Do not make notebook execution, live weather fetches, or
  legacy runtime checks part of the routine review path.
- Preserve the explicit producer-side boundary between persisted demand
  artifacts and sampled weather families. Do not merge the weather and demand
  artifacts or blur the required weather-driver contract.
- Keep cooling-service choice, district-cooling settlement, and blackout
  semantics simulator-side. Do not couple service-path behavior into demand
  fitting, artifact loading, or demand-family sampling.
- If optional notebook, live-fetch, or environment-sensitive follow-up checks
  are unavailable, document that in the feature quickstart or final response
  instead of widening the base environment requirements.

## Current TPM Planning Feature Guidance

- For `009-tpm-planning`, keep default validation offline and fixture-backed.
  Required current SPFlow, Pyomo, and HiGHS checks are part of the routine
  review path, but keep imports lazy and do not require notebooks, network
  services, commercial solver licenses, or legacy runtime checks.
- Preserve the explicit boundary between simulator-owned dataset export,
  TPM-owned artifact/query metadata, and planning-owned decision validation
  and solve behavior.
- Keep `shortfall` semantics library-owned and derived from simulator export
  inputs. Do not move outage, blackout, or broader simulator semantics into
  TPM fitting or planning assembly.
- Preserve battery-and-solar-only first-release planning scope unless the
  active spec expands it explicitly.
- Treat missing or incompatible required SPFlow, Pyomo, or HiGHS dependencies
  as validation failures. Gurobi and legacy parity checks remain optional; if
  unavailable, document them without weakening the required backend suite.

## Useful Checks

Run only the checks relevant to the files changed:

```bash
uv run pytest tests/unit/demand tests/integration/demand tests/integration/simulator
uv run pytest tests/unit/weather tests/integration/weather tests/integration/simulator
uv run pytest tests/unit/planning tests/unit/tpm tests/integration/planning tests/integration/tpm
uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.weather; import open_energy_lab.demand; import open_energy_lab.simulator; import open_energy_lab.tpm; import open_energy_lab.planning"
rg "from legacy|import legacy" src/open_energy_lab/weather src/open_energy_lab/demand src/open_energy_lab/simulator src/open_energy_lab/tpm src/open_energy_lab/planning tests/unit/weather tests/unit/demand tests/unit/tpm tests/unit/planning tests/integration/weather tests/integration/demand tests/integration/simulator tests/integration/planning docs/migration

cd legacy/old_tpm && cargo test
cd legacy/old_tpm && python scripts/test_battery_consistency.py
cd legacy/old_tpm && pytest src_py/tpm/spn/test_tangent_lower_bound.py
cd legacy/old_tpm && ./scripts/test_data_validation.sh --test-type automatic
```

If a check cannot be run because of solver licenses, GPU/SLURM requirements,
W&B access, missing datasets, dependency setup, or optional live weather
fetch requirements, document that explicitly in the final response or feature
quickstart.
