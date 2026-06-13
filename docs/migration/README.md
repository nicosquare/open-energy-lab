# Migration Documentation

Migration notes define how behavior may move from `legacy/*` into the unified
library, including API maturity, dependency classification, fixture provenance,
parity validation, and environment assumptions.

## Current Native Package References

- `controller-pack.md`: preserve/improve/reject decisions, shipped controller
  behavior, fixture evidence, and exact legacy references for
  `open_energy_lab.control`
- `visualization-traces.md`: shipped inspection/reporting behavior, focused
  same-family comparison scope, experimental plotting split, and validation
  outcomes for `open_energy_lab.visualization`
- `api-maturity.md`: stable public API promotion for
  `open_energy_lab.control` package-root exports plus the visualization
  stable-versus-experimental boundary
- `dependency-policy.md`: import-light dependency classification and rejected
  runtime stacks for the controller pack and visualization feature
- `parity-validation.md`: controller-pack validation minimums and preserved-path
  regression rules
- `environment-assumptions.md`: default local validation environment and skip
  rules for non-core capabilities

## Visualization Review Path

For the `006-visualization-traces` feature, read the migration docs in this
order:

1. `visualization-traces.md` for the shipped inspection/reporting surface,
   same-family comparison scope, experimental plotting split, fixture set, and
   recorded validation outcomes.
2. `api-maturity.md` for the stable package-root visualization imports versus
   focused comparison and experimental plotting module imports.
3. `dependency-policy.md` for the import-light visualization dependency
   boundary and optional plotting guidance.
4. `fixture-provenance.md` together with
   `tests/fixtures/visualization/README.md` for the committed fixture record
   requirements and refresh expectations.

This review path keeps the visualization feature anchored to shipped library
behavior, not to the earlier scaffolding state.

## Working Rule

Future migration specs must identify target library paths, validation paths,
legacy source paths, preserved or rejected behavior, and dependency boundaries
before implementation begins.
