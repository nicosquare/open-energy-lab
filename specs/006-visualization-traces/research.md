# Research: Visualization And Trace Inspection MVP

## Decision 1: Build visualization as an adapter over existing deterministic results

**Decision**: `open_energy_lab.visualization` will consume existing
deterministic simulator and controller-driven result objects rather than
changing how `open_energy_lab.simulator` or `open_energy_lab.core` generate
them.

**Rationale**: The feature is support infrastructure. It adds inspection and
presentation value without widening simulator ownership or introducing a
second execution path. This preserves the established architecture:
`simulator/core/control` generate results, `visualization` renders and compares
them.

**Alternatives considered**:

- Add visualization-specific fields directly to simulator execution paths:
  rejected because it widens simulator responsibility.
- Require controllers to emit richer visualization payloads: rejected because
  it couples presentation concerns to controller behavior.

## Decision 2: Keep inspection/reporting stable and plotting experimental

**Decision**: The package root will expose one stable inspection/reporting
surface, while static plotting support will live in an experimental optional
layer.

**Rationale**: Canonical inspection is the long-term reusable contract that
future features need. Plotting details are more likely to evolve as the
library learns what reviewers and downstream workflows need. Splitting
maturity lets the core contract stabilize now without freezing plotting
choices too early.

**Alternatives considered**:

- Make the entire package stable immediately: rejected because plotting
  details are still exploratory.
- Keep the entire package experimental: rejected because that would weaken the
  value of standardizing inspection now.

## Decision 3: Plot from existing in-memory or persisted outputs without rerunning simulation

**Decision**: Both inspection and plotting will operate on supported existing
run outputs. They may consume objects already in memory or load supported
persisted outputs later, but they will never rerun a scenario to create a
plot.

**Rationale**: The user explicitly wants plotting to fit multiple workflows,
not just the process that originally ran the simulation. Reusing supported
outputs keeps visualization deterministic and avoids hidden execution work.

**Alternatives considered**:

- Plot only from live in-memory results: rejected because it ties
  visualization to the execution process.
- Introduce a dedicated visualization-specific artifact format: rejected for
  the MVP because the feature should adapt supported stored outputs rather than
  invent a parallel artifact ecosystem.

## Decision 4: Restrict comparison to the same scenario family in the MVP

**Decision**: Detailed comparison support is limited to runs from the same
scenario family. Cross-family comparison is explicitly unsupported in this
MVP.

**Rationale**: Same-family comparison keeps alignment rules objective and
testable. Cross-family comparison would quickly devolve into weak,
summary-only heuristics or misleading partial alignments without enough value
for the first release.

**Alternatives considered**:

- Support reduced cross-family summary comparison: rejected because it adds a
  second comparison standard with weaker semantics.
- Compare any overlapping traces regardless of scenario family: rejected
  because it risks misleading output and brittle tests.

## Decision 5: Limit weather reporting to simulator-exposed fields

**Decision**: Weather reporting includes only the weather variables already
exposed by supported simulator scenarios.

**Rationale**: The visualization feature should not expand weather modeling or
invent synthetic environmental inputs. It should only make the existing
weather context inspectable alongside PV and net-grid behavior.

**Alternatives considered**:

- Add derived or inferred weather fields in visualization: rejected because it
  widens domain semantics outside the simulator.
- Omit weather from the MVP: rejected because it would make PV behavior harder
  to understand and validate.

## Decision 6: Keep required runtime dependencies unchanged

**Decision**: The stable inspection/reporting surface introduces no new
required runtime dependencies. Any plotting backend remains optional and must
be isolated behind plotting-specific imports and tests.

**Rationale**: The project foundation requires a minimal core library. The
value of the feature drops sharply if ordinary imports start requiring
heavyweight presentation stacks. Optional isolation preserves usability in the
same environments that already support current library work.

**Alternatives considered**:

- Add a required plotting dependency to the base package: rejected because it
  weakens the import boundary.
- Defer all plotting until a later feature: rejected because the user wants
  a plotting-capable MVP now.

## Decision 7: Validate through fixtures and focused integration tests, not notebook workflows

**Decision**: The MVP will prove behavior through deterministic fixtures,
package-boundary tests, persisted-output checks, and focused integration tests
instead of notebook review or dashboard-style manual validation.

**Rationale**: Tests and fixtures are reproducible and fit the existing
library workflow. Notebook-only review would make inspection behavior harder
to trust and harder to regression-test.

**Alternatives considered**:

- Use notebooks as the primary validation path: rejected because it is not
  reproducible enough for a stable library contract.
- Validate only unit-level formatting helpers: rejected because the feature
  must prove it works against real simulator outputs.
