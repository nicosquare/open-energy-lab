# Data Model: Unified Library Foundation

This feature defines governance entities rather than runtime simulation data
structures. The entities below describe how future migrations should be planned,
reviewed, and validated.

## Library Package

**Fields**: `namespace`, `source_root`, `test_root`, `module_areas`,
`public_api_policy`, `dependency_policy`.

**Relationships**: Owns Module Areas and Public API Surfaces. References
Dependency Classification Records and Migration Specs.

**Validation rules**:

- `namespace` is `open_energy_lab`.
- `source_root` is `src/open_energy_lab`.
- `test_root` is `tests`.
- New reusable code must target the library package, not `legacy/*`.

## Module Area

**Fields**: `name`, `path`, `purpose`, `status`, `allowed_content`,
`out_of_scope_content`.

**Relationships**: Belongs to Library Package. May contain Public API Surfaces
and Optional Capabilities.

**Validation rules**:

- Planned module areas are `simulator`, `core`, `planning`, `control`,
  `visualization`, and `experimental`.
- This foundation may scaffold module areas but must not add algorithm
  implementations.
- Energy primitives are assigned to `simulator` for the next migration unless a
  later spec changes the boundary.

## Public API Surface

**Fields**: `import_path`, `maturity`, `documentation_path`, `tests`,
`dependency_boundary`, `promotion_record`.

**Relationships**: Belongs to a Module Area. May depend on Optional
Capabilities only through documented boundaries.

**Validation rules**:

- Documented `open_energy_lab.*` imports are stable public API.
- `open_energy_lab.experimental.*` imports are explicitly unstable.
- Private modules use a leading underscore and are not public API.
- Promotion from experimental/private to stable requires review, tests,
  documentation, and dependency classification.

**State transitions**:

- `private` -> `experimental` when a migration needs importable incubation.
- `experimental` -> `stable` after explicit promotion review.
- `stable` -> `deprecated` only through a documented compatibility decision.

## Optional Capability

**Fields**: `name`, `module_path`, `dependency_records`, `activation_method`,
`offline_behavior`, `environment_requirements`.

**Relationships**: Groups one or more Dependency Classification Records.

**Validation rules**:

- Optional capabilities must not be imported by core package import paths.
- External services and hardware assumptions must have documented failure or
  skip behavior.
- Solver-backed, W&B, GPU/SLURM, TorchRL, notebook, real-data API, and Rust
  workflows are optional unless a future spec explicitly promotes them.

## Environment Definition

**Fields**: `environment_file`, `package_manager`, `python_version`,
`base_dependencies`, `dev_dependencies`, `lockfile`, `excluded_dependencies`.

**Relationships**: Supports Library Package, Optional Capabilities, and
Dependency Classification Records.

**Validation rules**:

- The base environment is declared in `environment.yml`.
- Conda provides the base research environment and Python interpreter.
- uv manages Python project dependencies, dev dependencies, editable
  installation, locking, and command execution.
- The foundation base environment includes Python, uv, and bootstrapping tools
  only.
- Heavy optional stacks must not be added to the foundation base environment.

## Dependency Classification Record

**Fields**: `dependency_name`, `classification`, `used_by`, `rationale`,
`import_boundary`, `install_extra`, `fallback_or_skip_behavior`.

**Allowed classifications**: `core`, `optional`, `external-service-backed`,
`hardware-bound`, `legacy-only`.

**Validation rules**:

- Every dependency added by a future migration must have exactly one primary
  classification.
- Core dependencies require stronger justification than optional dependencies.
- Legacy-only dependencies may be used to run reference checks but must not be
  required by the unified package.

## Legacy Reference

**Fields**: `legacy_project`, `source_paths`, `behavior_summary`,
`known_limitations`, `selected_for_migration`.

**Relationships**: Cited by Migration Specs and Parity Cases.

**Validation rules**:

- Source paths must be exact enough for review.
- Legacy conventions are evidence, not target architecture.
- Whole-file migration without behavior selection is invalid.

## Migration Spec

**Fields**: `target_module`, `legacy_references`, `preserve`, `improve`,
`reject`, `api_maturity`, `dependency_records`, `parity_cases`,
`documentation_updates`.

**Relationships**: Produces or changes Module Areas, Public API Surfaces,
Optional Capabilities, Parity Cases, and Fixture Provenance Records.

**Validation rules**:

- Must cite behavior to preserve, improve, and reject.
- Must define validation evidence before implementation.
- Must not make heavy dependencies core without explicit justification.
- Must not treat broad simulator-level parity as mandatory when the migration
  intentionally adopts cleaner logic outside the named preserved behavior.

## Parity Case

**Fields**: `name`, `legacy_reference`, `target_behavior`, `inputs`,
`expected_outputs_or_properties`, `tolerances`, `environment`,
`automation_level`.

**Relationships**: May use Fixture Provenance Records and Legacy References.

**Validation rules**:

- Must be reproducible by tests, deterministic configs, documented equations,
  snapshots, focused smoke checks, or documented manual limitations.
- Should be used only for explicitly preserved behavior rather than as a proxy
  for full architectural parity.
- Long-running training or solver workflows should provide focused smoke checks
  when full parity cannot run locally.

## Fixture Provenance Record

**Fields**: `fixture_path`, `origin`, `generation_command`, `seed`,
`source_data`, `license_or_access_notes`, `expected_use`, `refresh_policy`.

**Relationships**: Supports Parity Cases and tests.

**Validation rules**:

- Small curated fixtures may live under `tests/fixtures`.
- Generated fixtures require provenance and regeneration notes.
- Large generated outputs and external datasets should not be committed unless a
  future spec explicitly justifies them.

## Simulator Preparation Record

**Fields**: `target_module`, `composition_model`, `candidate_components`,
`data_policy`, `adapter_policy`, `first_validation_case`, `excluded_work`.

**Relationships**: Seeds the next simulator migration spec.

**Validation rules**:

- `composition_model` is a component graph.
- Candidate components include batteries, PV, loads, tariffs, time grids,
  units, buildings, generators, markets, and networks.
- Synthetic data is first-class; real data uses templates and optional adapters.
- TorchRL compatibility is an optional adapter.
- Battery arbitrage is the first validation target.
- Simulator implementation is excluded from this foundation feature.
