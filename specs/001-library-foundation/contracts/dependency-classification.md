# Contract: Dependency Classification

Every future migration that adds or relies on a dependency must include a
classification record.

## Classification Record

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

## Classifications

`core`: Required for ordinary import and basic use of the library. Core
dependencies require explicit justification and should be small, stable, and
portable.

`optional`: Required only for a named capability or adapter. Optional
dependencies should be isolated behind module-level imports, extras, adapter
entry points, or clear error messages.

`external-service-backed`: Requires a network service, account, credential, or
API such as W&B or ENTSO-E. These capabilities need documented disabled/offline
behavior where practical.

`hardware-bound`: Requires GPU, SLURM/HPC, or other execution environment
assumptions. These capabilities must not block core imports or ordinary tests.

`legacy-only`: Needed only to run or compare against legacy reference behavior.
These dependencies must not be required by the unified package.

## Import Boundary Rules

- `import open_energy_lab` must not require optional research stacks.
- Stable public API imports must not trigger W&B login, solver license checks,
  GPU initialization, SLURM commands, Rust compilation, or external data API
  calls.
- Optional capability modules may raise clear dependency errors when used
  without their required extras or environment.
- Tests that require unavailable services, hardware, or licenses must be marked
  or separated so the default test subset remains runnable locally.

## Known Legacy Dependency Families

Future specs should classify these before use:

- Solver and optimization: Pyomo, Gurobi, CPLEX/docplex.
- Probabilistic modeling: SPFlow and SPN/MIO support libraries.
- RL libraries and environment tooling: PyTorch, TorchRL.
- Legacy-only environment references: CityLearn.
- Experiment workflow: W&B, notebooks, sweep configs.
- Execution environment: GPU, CUDA, SLURM/HPC scripts.
- Rust parity and performance: Rust toolchain, cargo, binding generators.
