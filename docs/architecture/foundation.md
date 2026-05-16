# Open Energy Lab Foundation Architecture

Open Energy Lab is being organized as a Python-first research library. New
reusable product code belongs under `src/open_energy_lab`; `legacy/old_tpm` and
`legacy/fed_trpo` remain reference material unless a later migration or
maintenance spec explicitly authorizes a change there.

## Package Layout

```text
src/
└── open_energy_lab/
    ├── __init__.py
    ├── py.typed
    ├── experimental/
    ├── simulator/
    ├── core/
    ├── planning/
    ├── control/
    └── visualization/
```

The documented `open_energy_lab.*` namespace is the target public package
surface. Immature migrations start under `open_energy_lab.experimental` or
private modules until a migration or capability spec promotes them.

The current module scaffolds are documentation-only boundaries. They define the
places where later specs may add validated behavior, but this foundation does
not migrate simulator, TPM, RL, optimization, weather, notebook, W&B, GPU/SLURM,
Rust binding, planning, or control algorithms.

## Test Layout

```text
tests/
├── unit/
├── integration/
├── parity/
└── fixtures/
```

Unit tests cover import contracts, package boundaries, dependency isolation, and
small deterministic behavior. Integration tests cover interactions once
implemented capabilities exist. Parity tests compare migrated behavior against
legacy references, documented equations, snapshots, or deterministic smoke
checks. Fixtures live under `tests/fixtures` only when they include provenance
and regeneration notes.

## Environment Strategy

`environment.yml` defines the minimal conda base environment with Python, uv,
pip, and conda-forge. Conda provides the interpreter and research-environment
boundary; uv manages Python project dependencies, dev dependencies, editable
installation, locking, and command execution through `pyproject.toml`.

The foundation keeps the core import path light. Solver stacks, TorchRL,
PyTorch, CityLearn, SPFlow, W&B, notebooks, GPU/SLURM workflows, Rust tooling,
and external data APIs are optional capabilities unless a later spec explicitly
promotes one.

## Roadmap Modules

- `open_energy_lab.simulator`: first likely migration area for simulator
  components such as batteries, PV, loads, tariffs, time grids, units, and
  scenarios.
- `open_energy_lab.core`: future reusable methods such as TPM, RL, MPC,
  optimization-based methods, and rule-based approaches.
- `open_energy_lab.planning`: future planning interfaces or contracts only in
  this foundation.
- `open_energy_lab.control`: future control interfaces or contracts only in
  this foundation.
- `open_energy_lab.visualization`: lower-priority future tools for inspecting
  simulator and control-task behavior.

Planning and control implementations, concrete controllers, planners, RL
agents, optimization models, and training loops require later migration or
capability specs.

## Legacy Reference Boundary

Legacy directories are evidence, not target architecture:

- `legacy/old_tpm`: Rust/Python simulation, SPN/MIO, weather, and experiment
  references.
- `legacy/fed_trpo`: federated RL, PPO/TRPO, CityLearn, sweep, W&B, and SLURM
  workflow references.

Future migrations must cite exact legacy source paths, identify behavior to
preserve, improve, or reject, classify dependencies, and define validation
evidence before behavior is moved into `src/open_energy_lab`.
