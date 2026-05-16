# Research: Unified Library Foundation

## Decision: Use `open_energy_lab` with a `src` Layout

**Decision**: The unified package namespace is `open_energy_lab`, with reusable
library code under `src/open_energy_lab` and tests under `tests`.

**Rationale**: A single package namespace makes future migrations converge into
one import surface instead of preserving legacy repository boundaries. A `src`
layout reduces accidental imports from the working tree and makes packaging
checks closer to installed-package behavior.

**Alternatives considered**: Keeping code under `legacy/*` would preserve old
architecture as law. Multiple top-level packages would make early integration
harder. A flat package layout is simpler but weaker for packaging validation.

## Decision: Define Roadmap Modules Without Migrating Algorithms

**Decision**: Reserve module areas for `simulator`, `core`, `planning`,
`control`, `visualization`, and `experimental`, but keep this feature limited to
scaffold, governance, and documentation.

**Rationale**: The long-term library needs clear destinations for simulation,
planning, control, and reusable methods, but migrating behavior before the
contracts exist would copy legacy coupling into the new library.

**Alternatives considered**: Migrating the simulator immediately would skip the
foundation review. Deferring all module names would leave future specs without
useful target paths.

## Decision: Treat Simulator as the First Migration Area

**Decision**: The next likely migration should prepare
`open_energy_lab.simulator` around component-graph scenarios. Energy primitives
such as batteries, PV, loads, tariffs, time grids, units, markets, and
scenarios belong inside the simulator boundary unless a future spec changes it.

**Rationale**: Both legacy projects depend on simulation concepts, and the
user's near-term research cases need reusable environments before TPM, RL,
planning, or control integrations can be cleanly unified.

**Alternatives considered**: Starting with TPM or RL would recreate a method
module before the shared environment abstraction exists. Making energy
primitives top-level concepts would prematurely commit to a broad domain model.

## Decision: Public API Requires Explicit Promotion

**Decision**: Documented imports under `open_energy_lab.*` are stable public API.
Immature migrations start under `open_energy_lab.experimental` or private
modules. Promotion to stable API requires review of tests, docs, dependency
boundaries, and migration evidence.

**Rationale**: Research code needs room to incubate without making every early
import path permanent.

**Alternatives considered**: Making all package imports public would slow
refactoring. Keeping everything private would make the library unusable for
early research consumers.

## Decision: Classify Dependencies Per Migration

**Decision**: No scientific, solver, RL, logging, notebook, GPU, SLURM, data
API, or Rust dependency becomes core by default. Each future migration proposes
and justifies dependencies as core, optional, external-service-backed,
hardware-bound, or legacy-only.

**Rationale**: Legacy projects include valuable but heavy dependencies such as
TorchRL, PyTorch, CityLearn, Pyomo, Gurobi, CPLEX/docplex, SPFlow, W&B,
Jupyter, GPU tooling, and SLURM scripts. Making them unconditional would make
basic import and testing fragile.

**Alternatives considered**: A broad research dependency bundle is convenient
for experiments but too expensive for ordinary library use. A strict
stdlib-only rule would block legitimate future capabilities.

## Decision: Use Conda for the Base Environment and uv for Python Dependencies

**Decision**: Define `environment.yml` as a minimal conda environment containing
Python, uv, and basic bootstrapping tools only. Define `pyproject.toml` as the
uv-compatible Python project configuration with no runtime dependencies in the
foundation and a dev dependency group for pytest.

**Rationale**: Conda is a practical boundary for research environments and
future native/system-level dependencies, while uv gives faster, reproducible
Python dependency management, editable installs, locking, and command
execution. Keeping the foundation environment minimal prevents solver, RL,
notebook, W&B, GPU, SLURM, and Rust tooling from becoming implicit core
requirements.

**Alternatives considered**: Conda-only dependency management is familiar but
less aligned with modern Python packaging and lock workflows. uv-only
environments are lighter but do not give the preferred conda boundary for
future research stacks. Adding heavy optional dependencies now would violate
the foundation dependency policy.

## Decision: Require Reproducible Migration Evidence

**Decision**: Future migrations must cite exact legacy paths and provide
validation evidence such as fixture-based tests, deterministic configs,
documented equations, snapshots, focused smoke runs, or explicit limitations.

**Rationale**: Legacy behavior is valuable only when the new implementation can
be checked. Some workflows cannot be fully automated locally because of solver
licenses, W&B access, GPUs, SLURM, network APIs, or missing generated data, so
the policy must allow documented partial evidence.

**Alternatives considered**: Full bit-for-bit parity is unrealistic for
stochastic and environment-bound research workflows. Manual-only validation is
not reproducible enough.

## Decision: Keep Fixtures Small and Provenanced

**Decision**: Small curated generated artifacts may live under `tests/fixtures`
only with provenance, regeneration notes, and intended use. Large generated
outputs, training runs, solver caches, and notebook outputs should remain
external or reproducible through documented commands.

**Rationale**: Tests need stable evidence, but the repository should not become
a dump of generated research artifacts.

**Alternatives considered**: Rejecting all generated artifacts would make some
legacy parity checks hard. Committing arbitrary outputs would hide provenance
and bloat the project.

## Decision: Notebooks Are Examples or References

**Decision**: Notebooks may document experiments, exploration, or examples, but
reusable behavior must move into library modules before it is treated as product
code.

**Rationale**: Both legacy projects used notebooks for experiments. The unified
library needs importable, testable behavior rather than notebook-only logic.

**Alternatives considered**: Keeping notebooks as implementation units would
preserve legacy workflow friction. Banning notebooks would remove a useful
research communication format.

## Decision: Isolate Solver, W&B, GPU, SLURM, TorchRL, and Data API Workflows

**Decision**: Solver-backed optimization, W&B logging, GPU/SLURM execution,
TorchRL wrappers, and real-data adapters such as ENTSO-E must be optional
capabilities with documented disabled/offline behavior where practical.

**Rationale**: These workflows are important for research but should not be
requirements for importing the package, running basic tests, or using synthetic
simulation cases.

**Alternatives considered**: Making these workflows core would match some
legacy experiments but would make the foundation brittle. Excluding them
entirely would conflict with the project vision.

## Decision: Use Rust as Reference Until a Binding Spec Exists

**Decision**: Rust code in `legacy/old_tpm` may support parity checks,
performance comparisons, or future bindings, but the foundation does not make
Rust mandatory for ordinary Python usage.

**Rationale**: The user still values a Rust simulator direction, but the first
library foundation is Python-first and must remain easy to import.

**Alternatives considered**: Requiring Rust immediately would increase setup
cost before the simulator API exists. Ignoring Rust would discard useful
reference behavior.
