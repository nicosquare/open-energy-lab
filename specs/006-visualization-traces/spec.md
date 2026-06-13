# Feature Specification: Visualization And Trace Inspection MVP

**Feature Branch**: `006-visualization-traces`  
**Created**: 2026-06-09  
**Status**: Draft  
**Input**: User description: "Specify the next Open Energy Lab feature as a
Visualization And Trace Inspection MVP under
`src/open_energy_lab/visualization`."

## Purpose *(mandatory)*

Define the first reusable visualization and inspection surface for Open Energy
Lab so deterministic simulator and controller outputs can be reviewed,
compared, and communicated through one canonical library-owned workflow rather
than through ad hoc test helpers, notebooks, or debug scripts.

The outcome is a bounded inspection layer that standardizes how supported run
outputs expose trace views, summaries, weather-aware context, and comparison
results, including basic static plots for supported single-run traces, without
changing simulator execution semantics or introducing a heavy UI-oriented
dependency footprint.
Supported plots are generated from existing run outputs rather than by
triggering a fresh simulation workflow. Those run outputs may already be in
memory or may be loaded later from a supported persisted output.

## Clarifications

### Session 2026-06-09

- Q: Should weather reporting in this MVP add new weather-model scope? → A: No.
  Weather reporting is limited to weather variables already exposed by the
  simulator.
- Q: Should the visualization MVP be positioned as dashboard or notebook UI
  work? → A: No. It is a lightweight library inspection surface, not a
  dashboard-first or notebook-first feature.
- Q: Should the MVP require rendered plotting support? → A: Inspection and
  tabular summaries plus basic static plots for supported single-run traces.
- Q: Should plotting be part of the always-available base visualization
  surface? → A: No. Core inspection and reporting stay always available, while
  plotting is supported through an optional plotting layer that can render
  from existing run outputs without requiring re-simulation.
- Q: Should the MVP compare runs only within the same scenario family? → A:
  Yes. Full comparison support is limited to runs from the same scenario
  family.
- Q: Should plotting support only in-memory run results, or also persisted
  run outputs loaded later? → A: It supports both in-memory results and
  supported persisted run outputs loaded later.
- Q: What API maturity should the visualization surface have in this MVP? → A:
  Core inspection and reporting are stable, while optional plotting remains
  experimental.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability
- **Target surface**: Public library API for deterministic result inspection,
  comparison, and presentation-ready summaries
- **Legacy reference paths**: None
- **New-code location**:
  - `src/open_energy_lab/visualization`
  - `tests/unit/visualization`
  - `tests/integration/visualization`
  - `docs/migration`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect A Single Deterministic Run (Priority: P1)

A maintainer or library consumer wants to inspect a simulator or
controller-driven run through a stable trace-inspection surface so they can
review key run behavior without writing bespoke access logic for every output
shape.

**Why this priority**: The simulator and controller surfaces are now large
enough that output review has become a recurring maintenance workflow. A
canonical inspection surface prevents fragmented trace handling before more
features multiply result consumers.

**Independent Test**: A deterministic arbitrage result can be passed through
the public visualization surface and exposes a stable set of run summaries and
trace views for battery state, dispatch behavior, prices, and settlement
without requiring direct access to simulator internals, and can also produce
basic static plots for supported single-run traces.

**Acceptance Scenarios**:

1. **Given** a deterministic arbitrage run produced by the native simulator,
   **When** a maintainer inspects it through the public visualization surface,
   **Then** the important traces and aggregate outcomes are available through a
   canonical inspection shape rather than ad hoc result traversal.
2. **Given** a controller-driven run produced through the existing controller
   evaluation flow, **When** it is inspected, **Then** requested dispatch,
   realized dispatch, battery state, price context, and settlement-relevant
   outcomes are presented consistently with simulator-owned semantics.
3. **Given** a supported run result is inspected repeatedly, **When** the same
   inspection request is repeated, **Then** the reported trace ordering,
   summary values, and formatting remain deterministic within the documented
   numeric tolerance.
4. **Given** a supported single-run result, **When** a maintainer requests a
   visual rendering, **Then** the visualization surface can produce basic
   static plots for the supported traces in a deterministic review workflow.
5. **Given** a previously generated supported run result, **When** a
   maintainer requests static plots from the optional plotting layer, **Then**
   the plots are produced from the existing run output without requiring the
   scenario to be simulated again.
6. **Given** a supported persisted run output loaded after the original
   simulation completed, **When** a maintainer requests inspection or static
   plotting, **Then** the visualization surface can operate on that loaded
   output without requiring the scenario to be simulated again.

---

### User Story 2 - Inspect Weather-Aware PV Runs (Priority: P2)

A maintainer wants battery, load, PV, and weather-backed runs to be reviewable
through the same inspection layer so environmental drivers and resulting
energy-balance behavior can be understood together rather than through
separate domain-specific helpers.

**Why this priority**: `BatteryLoadPVScenario` is already part of the migrated
simulator surface, and PV behavior is harder to validate if weather context is
not visible alongside the resulting traces.

**Independent Test**: A deterministic battery + load + PV run can be inspected
through the public visualization surface and includes battery, load, PV, net
grid, settlement, and the weather variables already exposed by the simulator
for that run family.

**Acceptance Scenarios**:

1. **Given** a deterministic `BatteryLoadPVScenario` run, **When** it is
   inspected, **Then** the inspection surface shows load, PV, net-grid, and
   battery traces together with the weather variables already exposed by the
   simulator for that scenario family.
2. **Given** a supported weather-backed run, **When** the maintainer reviews
   the inspection output, **Then** they can understand how environmental
   context aligns with PV-related run behavior without inferring hidden weather
   assumptions.
3. **Given** a supported run family that does not expose weather variables,
   **When** it is inspected, **Then** the absence of weather reporting is
   explicit and deterministic rather than treated as an error.

---

### User Story 3 - Compare Deterministic Runs Side By Side (Priority: P2)

A maintainer wants to compare two supported runs through one reusable workflow
so controller changes, scenario adjustments, and preserved-path regressions can
be understood without hand-built comparison scripts.

**Why this priority**: As more controllers and scenario variants appear, the
ability to compare runs becomes part of ordinary review and regression work.

**Independent Test**: Two deterministic supported runs produced from the same
scenario family can be compared through the public visualization surface and
yield a stable comparison view covering trace-level and summary-level
differences.

**Acceptance Scenarios**:

1. **Given** two supported runs from the same scenario family, **When** a
   maintainer compares them, **Then** the comparison surface highlights
   differences in the relevant traces and summary outcomes through one
   canonical comparison shape.
2. **Given** two controller-driven runs on the same scenario inputs, **When**
   they are compared, **Then** requested dispatch, realized dispatch, battery
   behavior, net-grid behavior, and settlement-relevant differences are
   presented consistently.
3. **Given** two runs that are structurally incompatible for comparison,
   **When** a comparison is requested, **Then** the visualization surface
   rejects the request through an explicit and deterministic unsupported-case
   response.
4. **Given** two valid runs from different supported scenario families,
   **When** a comparison is requested, **Then** the visualization surface
   rejects the request as out of scope for the MVP rather than attempting a
   reduced cross-family comparison.

---

### User Story 4 - Preserve A Lightweight Inspection Boundary (Priority: P3)

A library consumer wants ordinary inspection imports to remain lightweight and
bounded so run review does not depend on notebooks, dashboards, external
services, or research-only environments.

**Why this priority**: Inspection is valuable only if it stays available in the
same lightweight environments that already support ordinary simulator and
controller usage.

**Independent Test**: Import-boundary validation proves that the supported
visualization surface loads in the baseline environment without requiring
notebook tooling, experiment tracking services, GPU/SLURM workflows, or
runtime `legacy/*` imports.

**Acceptance Scenarios**:

1. **Given** a baseline local environment for ordinary library use, **When**
   the supported visualization package is imported, **Then** it does not
   require notebooks, dashboards, W&B, GPU/SLURM tooling, external API
   clients, or runtime `legacy/*` imports.
2. **Given** future planning, forecasting, or tariff features are added,
   **When** they need run inspection, **Then** they can reuse the canonical
   visualization surface instead of introducing mandatory parallel inspection
   stacks.

### Edge Cases

- A run family exposes only a subset of standard traces, such as no PV series
  or no weather variables.
- Two valid runs are requested for comparison but differ in supported scenario
  family, trace lengths, or available series.
- A supported result contains optional controller-specific traces such as
  requested dispatch for some runs but not others.
- Floating-point values that differ only within the documented numeric
  tolerance must be presented deterministically and not create misleading
  comparison noise.
- A user requests weather reporting for a run family where the simulator does
  not expose weather variables.
- A trace is empty, one timestep long, or otherwise too small to support the
  full standard presentation workflow.
- A supported run can be inspected structurally but does not contain enough
  meaningful variation to justify every standard static plot.
- A plot is requested after simulation has already completed and the plotting
  layer must work from persisted or in-memory run outputs alone.
- A persisted run output contains enough supported inspection data for
  plotting, but the original simulator process is no longer available.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST define a reusable visualization and trace
  inspection surface under `src/open_energy_lab/visualization`.
- **FR-002**: The feature MUST provide a canonical inspection shape for
  supported deterministic run outputs so maintainers and library consumers do
  not need bespoke result-traversal code for ordinary review workflows.
- **FR-002A**: The canonical inspection surface MUST operate on supported
  deterministic run outputs whether they are already in memory or loaded later
  from a supported persisted output.
- **FR-003**: The feature MUST support inspection of outputs from the existing
  native simulator evaluation flow.
- **FR-004**: The feature MUST support inspection of outputs from the existing
  controller-driven evaluation flow without changing simulator-owned execution,
  feasibility, or settlement semantics.
- **FR-005**: The feature MUST expose inspection support for the currently
  migrated run families relevant to battery arbitrage and battery + load + PV
  evaluation.
- **FR-006**: The feature MUST include battery state, dispatch behavior, price
  context, and settlement-relevant outcomes in the inspection surface whenever
  those traces or summaries are present in a supported run result.
- **FR-007**: The feature MUST include load, PV, and net-grid reporting for
  supported run families that expose those traces.
- **FR-008**: The feature MUST report weather variables only when those
  variables are already exposed by the simulator for the inspected run family,
  and MUST NOT expand weather-model scope beyond reporting them.
- **FR-008A**: The feature MUST provide basic static plot support for
  supported single-run traces as part of the MVP visualization surface.
- **FR-008B**: The feature MUST support plotting through an optional plotting
  layer so core inspection and reporting remain available without mandatory
  plotting dependencies.
- **FR-008C**: The optional plotting layer MUST consume existing supported run
  outputs and MUST NOT require a fresh simulation run to generate plots.
- **FR-009**: The feature MUST provide a stable way to compare two supported
  runs from the same scenario family side by side through one canonical
  comparison surface.
- **FR-010**: The comparison surface MUST make unsupported comparison cases
  explicit and deterministic rather than inferring best-effort behavior from
  incompatible runs.
- **FR-011**: The feature MUST define deterministic presentation ordering and
  formatting for supported traces and summaries, including numeric values that
  differ only within the documented tolerance.
- **FR-012**: The feature MUST preserve the architectural boundary that
  `open_energy_lab.simulator` owns deterministic result generation,
  `open_energy_lab.core` owns controller-facing contracts,
  `open_energy_lab.control` owns shipped controller behavior, and
  `open_energy_lab.visualization` owns inspection and presentation helpers.
- **FR-013**: The feature MUST NOT change simulator physics, controller logic,
  settlement semantics, or weather semantics as part of visualization support.
- **FR-014**: The feature MUST keep ordinary visualization imports lightweight
  and MUST NOT require notebook tooling, dashboards, W&B, GPU/SLURM tooling,
  external API clients, or runtime `legacy/*` imports.
- **FR-015**: The feature MUST document the supported inspection surface,
  supported run families, deferred workflows, and API maturity for the new
  visualization package.
- **FR-015A**: The feature MUST publish the core inspection and reporting
  surface as stable for the MVP.
- **FR-015B**: The feature MUST publish the optional plotting layer as
  experimental for the MVP.
- **FR-016**: The feature MUST validate supported inspection and comparison
  behavior through deterministic tests and fixtures rather than relying on
  manual notebook review.
- **FR-017**: The feature MUST allow supported future workflows to reuse the
  same inspection surface instead of requiring workflow-specific trace
  presentation contracts.
- **FR-018**: The feature MUST treat dashboards, web applications, notebook-
  first workflows, experiment tracking integrations, and interactive GUI
  tooling as out of scope for this MVP.
- **FR-019**: The feature MUST treat rendered side-by-side comparison plots as
  deferred unless a later feature explicitly adds them, while still
  supporting structured run comparison in this MVP.

### Key Entities *(include if feature involves data or API design)*

- **Inspection View**: A canonical representation of one supported simulator or
  controller-driven run, including trace series, summary values, supported
  metadata, and explicit signals for unavailable optional sections.
- **Plot Request**: A deterministic request to render one or more supported
  static plots from an existing inspection view or compatible stored run
  output.
- **Persisted Run Output**: A supported stored representation of a
  deterministic run result that can be loaded later for inspection or
  plotting without rerunning the simulation.
- **Trace Series**: One ordered series within an inspection view, such as
  battery state, requested dispatch, realized dispatch, load, PV, net grid,
  price, or supported weather context.
- **Comparison View**: A canonical representation of the differences and
  aligned context between two supported inspection views from the same
  scenario family.
- **Summary Outcome**: A deterministic aggregate outcome associated with a run,
  such as settlement-relevant totals or other supported rollups needed for
  inspection and comparison.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Existing Open Energy Lab library surfaces that already
  produce deterministic supported run outputs
- **Optional dependencies**: Any heavier presentation tooling must remain
  optional and must not be required for ordinary imports of the canonical
  inspection surface
- **External services**: None
- **Hardware assumptions**: CPU-only execution is sufficient for supported
  inspection and comparison validation

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Maintainers can inspect supported deterministic runs from at
  least the current arbitrage and battery + load + PV scenario families through
  one canonical visualization surface without writing workflow-specific trace
  access helpers.
- **SC-001A**: Maintainers can generate basic static plots for supported
  single-run traces through the same visualization surface used for structured
  inspection.
- **SC-001B**: Maintainers can generate supported static plots from existing
  run outputs without re-running the simulation that produced those outputs.
- **SC-001C**: Maintainers can inspect and plot supported persisted run
  outputs after the original simulation process has ended.
- **SC-002**: Supported battery + load + PV inspection workflows expose both
  energy traces and the weather variables already exposed by the simulator in a
  single review flow.
- **SC-003**: Supported run comparisons produce deterministic trace-level and
  summary-level difference reporting across repeated runs with identical inputs
  and comparison requests.
- **SC-004**: Import-boundary validation proves that ordinary use of
  `open_energy_lab.visualization` does not require notebook tooling,
  dashboards, W&B, GPU/SLURM tooling, external API clients, or runtime
  `legacy/*` imports.
- **SC-005**: The feature documents one stable inspection surface that future
  planning, forecast, tariff, and controller features can reuse instead of
  replacing with parallel trace-presentation workflows.
- **SC-006**: The feature documentation clearly distinguishes stable
  inspection/reporting contracts from experimental plotting support so future
  changes do not blur the public maturity boundary.

## Assumptions

- Supported run outputs already contain or can expose enough deterministic
  information for a canonical inspection surface without changing simulator
  execution ownership.
- Weather-aware inspection is limited to scenario families where the simulator
  already exposes weather variables relevant to the run outcome.
- The first visualization MVP prioritizes inspection consistency and
  maintainability over richer interactive presentation workflows.
- Optional plotting consumes already available supported run outputs rather
  than owning or repeating simulator execution.
- Stable API commitments in this MVP apply to canonical inspection and
  reporting behavior, while plotting remains intentionally more flexible.
- Optional plotting consumes already available supported run outputs rather
  than owning or repeating simulator execution.
- Existing simulator and controller result families remain the initial scope;
  broader future workflows can adopt the same inspection surface later.
