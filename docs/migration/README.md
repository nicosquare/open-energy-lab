# Migration Documentation

Migration notes define how behavior may move from `legacy/*` into the unified
library, including API maturity, dependency classification, fixture provenance,
parity validation, and environment assumptions.

## Current Native Control Package References

- `controller-pack.md`: preserve/improve/reject decisions, shipped controller
  behavior, fixture evidence, and exact legacy references for
  `open_energy_lab.control`
- `api-maturity.md`: stable public API promotion for
  `open_energy_lab.control` package-root exports
- `dependency-policy.md`: import-light dependency classification and rejected
  runtime stacks for the controller pack
- `parity-validation.md`: controller-pack validation minimums and preserved-path
  regression rules
- `environment-assumptions.md`: default local validation environment and skip
  rules for non-core capabilities

## Working Rule

Future migration specs must identify target library paths, validation paths,
legacy source paths, preserved or rejected behavior, and dependency boundaries
before implementation begins.
