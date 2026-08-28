# Contract: Validation Evidence

## Required deterministic data

One small scalar fixture contains reviewable physical rows and declarations sufficient to exercise:

- decision $x$ with mathematical domain $[40,160]$ and observations covering a strict subset;
- explicitly unbounded normal demand retained in physical units;
- declared binary ordering with one value optionally absent from a focused training slice;
- a finite caller-selected compiler interval strictly inside the decision domain; and
- probes at domain/validity endpoints, inside the mathematical domain but outside training support,
  and outside compiler validity.

The fixture records a stable seed, fit configuration, backend/compiler versions, feature order,
sidecar SHA-256, expected transforms, interval derivations, and the numerical tolerance associated
with each approximate assertion. This contract intentionally does not prescribe sample counts,
parity-grid size, or a new global threshold.

## Unit evidence

Focused tests cover:

- all five continuous mathematical states, including fixed endpoints and non-finite rejection;
- exact finite/one-sided endpoint membership and rejection of the adjacent outside representable
  value without borrowing an existing workflow tolerance;
- declaration omission versus explicit unknown versus explicit unbounded;
- decision/support role compatibility;
- rejection of unknown declaration keys, multi-feature references, and coupled constraint payloads;
- complete binary/category declaration and caller ordering with unobserved values;
- training support derived only from physical rows;
- declaration-aware typing before normalization;
- declared and legacy-inferred normalization/validation tables;
- forward and inverse transforms;
- v3 semantic round trip and manifest/sidecar agreement;
- v2 adaptation with frozen behavior and no strengthened claim;
- compiler interval presence, shape, containment, unused-entry, and no-fallback rules, including
  rejection of a loaded v2 fitted artifact even when the caller supplies an interval;
- physical/model breakpoint derivation and round trip; and
- endpoint acceptance and outside-validity rejection without clipping.

## Integration evidence

- Two datasets with different observed extrema and one declared domain transform a common probe
  identically while preserving different training support.
- A real current-SPFlow fit/query/reload uses finite scalar decision coordinates and identity-normal
  demand coordinates.
- Querying a declared but unobserved discrete value reaches backend evaluation without invented
  training support or an asserted probability requirement.
- Structurally marginalizing a continuous feature removes its approximation-domain requirement.
- A discrete-only retained graph compiles without continuous intervals.
- New compiled-v2 output succeeds from qualifying v3 fitted evidence and rejects loaded v2 or
  unknown/legacy-only fitted semantics with refitting guidance.
- Compiled physical evaluation agrees with native evaluation at focused declared probes under the
  existing per-test numerical contract and rejects out-of-region probes.
- A small offline Pyomo/HiGHS feasibility solve verifies physical-to-model decision linking.

Real SPFlow/Pyomo/HiGHS tests are collected in the existing required-backend workflow and are not
weakened into optional skips. Gurobi remains optional and is not evidence for accepting this feature.

The focused offline command in `examples/tpm_planning/run_declared_domains_pipeline.py` regenerates
or verifies only the declared-domain v3 manifest and sidecar. It is fixture maintenance evidence,
not a benchmark experiment or second implementation.

## Compatibility evidence

- Existing v2 manifests/sidecars retain their bytes and expected values.
- V2 loads expose unknown mathematical domains and legacy-inferred operational ranges/encodings.
- Existing v1 fixtures retain their rejection behavior.
- Legacy compiled v1 evaluation remains normalized-only.
- A loaded v2 fitted artifact cannot acquire new compiled-v2 physical validity; representative
  current compiler call sites refit as v3, select exact/marginalized treatment, or assert rejection.
- New v3 and compiled v2 output never masquerade as an older schema.

## Boundary evidence

- Importing `open_energy_lab`, `open_energy_lab.tpm`, and `open_energy_lab.planning` remains lazy.
- No runtime import from `legacy/*` is introduced.
- No network, notebook, GPU, commercial solver, or parent-repository write is required.
- `pyproject.toml` and `uv.lock` remain unchanged unless implementation discovers a demonstrable
  existing-environment defect; such a change requires separate review rather than silent scope
  expansion.
