<!-- SPECKIT START -->
Current Spec Kit plan: `specs/001-library-foundation/plan.md`

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

## Useful Checks

Run only the checks relevant to the files changed:

```bash
cd legacy/old_tpm && cargo test
cd legacy/old_tpm && python scripts/test_battery_consistency.py
cd legacy/old_tpm && pytest src_py/tpm/spn/test_tangent_lower_bound.py
cd legacy/old_tpm && ./scripts/test_data_validation.sh --test-type automatic
```

If a check cannot be run because of solver licenses, GPU/SLURM requirements,
W&B access, missing datasets, or dependency setup, document that explicitly in
the final response or feature quickstart.
