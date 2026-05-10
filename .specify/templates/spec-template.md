# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[###-feature-name]`  
**Created**: [DATE]  
**Status**: Draft  
**Input**: User description: "$ARGUMENTS"

## Purpose *(mandatory)*

[State the research/library outcome in plain language. Describe how this
feature moves Open Energy Lab toward a unified library rather than extending
legacy code.]

## Scope Classification *(mandatory)*

- **Feature type**: [Foundation / Migration / New library capability / Validation / Documentation / Tooling]
- **Target surface**: [Public library API / internal module / CLI/script / config schema / data artifact / experiment workflow]
- **Legacy reference paths**: [List paths under `legacy/old_tpm` or `legacy/fed_trpo`, or "None"]
- **New-code location**: [Target package path if known, or NEEDS CLARIFICATION until foundation spec defines it]

## User Scenarios & Testing *(mandatory)*

<!--
  User stories should be prioritized and independently testable.
  For migration stories, the "user" may be a researcher, library consumer, or
  maintainer validating behavior against legacy references.
-->

### User Story 1 - [Brief Title] (Priority: P1)

[Describe the user journey or research workflow in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe the smallest test or validation case that proves this story works independently]

**Acceptance Scenarios**:

1. **Given** [initial state/input/config], **When** [action/API call/command], **Then** [expected outcome]
2. **Given** [legacy reference or edge input], **When** [new library behavior is exercised], **Then** [expected parity or improved behavior]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

- [Boundary input, missing config, invalid units, solver unavailable, GPU unavailable, no W&B login, missing dataset, random seed behavior]
- [Legacy behavior that should not be preserved because it is ambiguous, brittle, or undocumented]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST [specific library/research capability]
- **FR-002**: The feature MUST define its public API or explicitly state that it is internal only
- **FR-003**: The feature MUST identify any legacy behavior being preserved, replaced, or rejected
- **FR-004**: The feature MUST define reproducibility inputs: seeds, configs, fixtures, datasets, solver assumptions, and tolerances where applicable
- **FR-005**: The feature MUST avoid adding unconditional heavyweight dependencies to the core library unless justified by this spec

*Examples of marking unclear requirements:*

- **FR-006**: The target package namespace is [NEEDS CLARIFICATION: foundation spec has not chosen package name]
- **FR-007**: The parity tolerance is [NEEDS CLARIFICATION: metric and tolerance not specified]

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**: [Exact legacy files, notebooks, configs, or scripts]
- **Behavior to preserve**: [Inputs, outputs, equations, metrics, command semantics]
- **Behavior to improve or drop**: [Known bad practices, stale paths, fragile assumptions]
- **Parity evidence**: [Test fixture, snapshot, deterministic seed, legacy command, or documented equation]

### Key Entities *(include if feature involves data or API design)*

- **[Entity 1]**: [What it represents, key attributes, units, and relationships]
- **[Entity 2]**: [What it represents, key attributes, units, and relationships]

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: [Dependencies required by the unified library core]
- **Optional dependencies**: [TorchRL, PyTorch, CityLearn, Pyomo, Gurobi, CPLEX, SPFlow, W&B, Jupyter, etc.]
- **External services**: [W&B, data APIs, license servers, or "None"]
- **Hardware assumptions**: [CPU/GPU/SLURM requirements or "None"]

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: [Measurable library/API outcome]
- **SC-002**: [Validation or parity outcome, with tolerance when applicable]
- **SC-003**: [Reproducibility outcome, such as deterministic output from fixed seed/config]
- **SC-004**: [Maintainability outcome, such as dependency isolation or documented migration boundary]

## Assumptions

- [Assumption about target users, such as researchers using the library from Python]
- [Assumption about legacy code being reference-only unless explicitly migrated]
- [Assumption about unavailable solvers, datasets, GPUs, or external services]
- [Assumption about package layout or dependency manager, if not yet defined]
