# Dependency Policy

This policy classifies dependency families before future migrations add them to
`open_energy_lab`. The foundation stays importable without solver stacks,
experiment tracking, GPU tooling, notebook tooling, or legacy reference
toolchains.

## Classification Record

Future specs must record dependency decisions with a review trail like this:

```text
Dependency:
Requested by:
Target module:
Classification:
Import boundary:
Install mechanism:
Fallback or skip behavior:
External service, license, hardware, or scheduler assumptions:
Rationale:
Alternatives considered:
```

## Classification Types

`core`

Required for ordinary import and basic use of the library. Core dependencies
should stay small, stable, and portable.

`optional`

Required only for a named capability or adapter. Optional dependencies should
stay behind module-level imports, extras, or clear error messages.

`external-service-backed`

Requires a network service, account, credential, or API such as W&B or a
weather/data service. These capabilities need documented offline or disabled
behavior where practical.

`hardware-bound`

Requires GPU, SLURM/HPC, or another execution-environment assumption. These
capabilities must not block core imports or ordinary tests.

`legacy-only`

Needed only to run, compare, or validate legacy reference behavior. These
dependencies must not become required for the unified package.

## Import Boundary Rules

- `import open_energy_lab` must not require optional research stacks.
- Stable public API imports must not trigger W&B login, solver license checks,
  GPU initialization, SLURM commands, Rust compilation, or external data API
  calls.
- Optional capability modules may raise clear dependency errors when used
  without their required extras or environment.
- Tests that require unavailable services, hardware, or licenses must be
  marked or separated so the default test subset remains runnable locally.

## Known Dependency Families

Future specs should classify these before use:

- Solver and optimization: Pyomo, Gurobi, CPLEX/docplex.
- Probabilistic modeling: SPFlow and SPN/MIO support libraries.
- RL and environments: PyTorch, TorchRL, CityLearn.
- Experiment workflow: W&B, notebooks, sweep configs.
- Execution environment: GPU, CUDA, SLURM/HPC scripts.
- Rust parity and performance: Rust toolchain, cargo, binding generators.
