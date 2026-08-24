# Architecture Documentation

Architecture notes describe the target `open_energy_lab` package layout, public
library boundaries, module roadmap, and foundation decisions that guide future
migration work.

Reusable product code belongs under `src/open_energy_lab`; `legacy/*` remains
reference material unless a later spec explicitly authorizes otherwise.

- [ENTSO-E Transparency Platform R3 integration](./entsoe-transparency-platform.md)
- [RTE Balancing Energy 5.2 integration](./rte-balancing-energy.md)

## Feature 011 restoration-services map

- Source: additive restoration contracts in
  [`market`](../../src/open_energy_lab/market),
  [`control`](../../src/open_energy_lab/control), and
  [`simulator`](../../src/open_energy_lab/simulator), with live RTE acquisition
  isolated in `market/rte.py`.
- Design: [Feature 011 implementation plan](../../specs/011-afrr-mfrr-services/plan.md)
  and [source/replay contracts](../../specs/011-afrr-mfrr-services/contracts/).
- Example: [offline aFRR/mFRR replay and notebook](../../examples/restoration_services/README.md).

The architecture supports bounded, deterministic research scenarios. It does
not claim that public area aggregates are asset commands, and it provides no
production dispatch or reserve-bidding optimization.
