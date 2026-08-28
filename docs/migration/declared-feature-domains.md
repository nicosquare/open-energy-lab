# Declared TPM Feature Domains

Status: implemented by `014-declared-feature-domains`. New TPM fits persist schema v3 semantic
records. Existing schema v2 artifacts and compiled-v1 payloads remain supported through visibly
legacy compatibility paths.

## Why domains must be declared

Observed training extrema describe the rows that happened to be sampled. They do not establish a
decision's feasible set, a random variable's theoretical support, or the region where a compiler
approximation is valid. OEL now keeps four records separate:

1. the mathematical decision domain or distribution support;
2. the physical values observed during training;
3. the physical-to-model-coordinate normalization and its origin; and
4. a compiler approximation's physical and derived model-coordinate validity.

No record silently substitutes for another.

## Declaring mathematical domains

Callers may pass feature-domain records through the generic row-fit request, the planning-dataset
fit entry point, or the study-manifest fit entry point. Each record owns exactly one named feature
and must agree with that feature's role.

Continuous declarations support these shapes:

- finite `[lower, upper]`, including a fixed value where both endpoints are equal;
- lower-bounded `[lower, +unbounded)`;
- upper-bounded `(-unbounded, upper]`;
- explicitly unbounded; and
- unknown.

Unbounded endpoints are semantic states, not serialized floating-point infinities. All supplied
numeric endpoints and observations must be finite. Finite endpoints are closed and checked exactly;
values immediately outside them fail rather than being clamped or accepted by an implicit domain
tolerance.

Binary declarations contain exactly two distinct labels in caller order. Categorical declarations
contain the complete value set and an authoritative order. Training support records only values
actually observed, so declaring `("off", "on")` while observing only `"off"` does not fabricate an
`"on"` training row or probability mass.

A feature declaration cannot encode a coupled constraint. Capacity, shared budget, and storage
relations such as `sum(weight[i] * select[i]) <= capacity` remain caller-owned model constraints.
They must not be represented as one coordinate's bounds.

## Normalization

Finite non-fixed continuous mathematical domains use affine min-max normalization. Fixed domains
map their single valid physical value to model coordinate zero. Lower-bounded, upper-bounded,
unbounded, and explicitly unknown continuous declarations use identity normalization and retain
physical units. Binary and categorical declarations use their caller-defined ordered indices.

Two datasets with different observed extrema therefore map the same physical probe identically when
they share one finite declared domain. Compiler intervals never alter fitting or native-query
normalization.

## Omission, explicit unknown, and v2 compatibility

Omitting a declaration keeps the old operational behavior but labels it precisely:

- mathematical meaning is unknown with origin `omitted`;
- observed extrema or discrete values are training support;
- the old min-max, fixed-zero, or ordered-index transformation is `legacy-inferred`; and
- legacy native queries retain their observed-range/value restrictions.

Explicit unknown is different. It is caller-declared mathematical uncertainty, uses identity
normalization for a continuous feature, and accepts any finite query value because observed support
does not become a query boundary.

New fits write schema v3. Loaded schema v2 manifests remain v2 when reserialized, keep mixed-feature
metadata unchanged, preserve their sidecar integrity contract, and acquire no theoretical claim.
They must be refit from source rows with declarations before a new physical-validity compilation.
Schema v1 fitted artifacts continue to fail with existing refit guidance.

## Native-query diagnostics

Native validation occurs before SPFlow evaluation. Failures distinguish:

- non-finite evidence;
- decision-domain violations;
- distribution-support violations;
- declared binary or categorical membership violations; and
- legacy operational restrictions.

Legacy failures retain their established reasons such as `out_of_bounds`, `invalid_binary`, or
`unseen_category`, while `semantic_source="legacy-inferred"` prevents them from being reported as
mathematical-domain failures. A valid declared-domain query may lie outside observed training
support.

## Compiled-v2 approximation validity

A new compiled-v2 request consumes a fitted schema v3 artifact and one explicit physical interval
for every retained continuous approximation. Planning adapters structurally marginalize unused
features first, so marginalized continuous uncertainty and exact discrete features receive no
artificial interval.

Each interval has finite, positive width, identifies its caller source and encoding, and must lie
inside a retained continuous decision's finite declared decision domain. The compiler does not fall
back to training extrema, distribution support, legacy bounds, `[0, 1]`, or the entire decision
domain. Unknown features, discrete features, unused features, missing intervals, and intervals on
loaded v2 artifacts fail explicitly.

The persisted validity record includes physical and model-coordinate intervals, both breakpoint
lists, normalization parameters and provenance, feature identity and schema index, encoding, and
compiler versions. Relative breakpoint positions are applied within the physical interval and then
transformed by the fitted normalization; the approximation subset is not renormalized to `[0, 1]`.

Physical evaluation validates the physical interval, transforms the value, validates the derived
coordinate, and evaluates the curve. The internal coordinate path checks the recorded model interval
directly. Neither path clips or extrapolates. Existing compiled-v1 payloads remain normalized-only
and never acquire inferred physical validity.

Pyomo compilation exposes a bounded physical decision variable, a bounded model-coordinate
variable, and the affine or identity equality between them. Declared binary labels map to solver
states zero and one by caller order and decode to the original labels. Integer decision linking is
not part of this feature.

## Notebook walkthrough

`examples/tpm_planning/declared_feature_domains_walkthrough.ipynb` is an optional, thin
demonstration of these semantics. It reuses the committed schema-v3 fitted artifact and real SPFlow
sidecar rather than refitting or reimplementing the domain rules. It compares two observed supports
under one declared domain, exercises unbounded and unobserved-discrete cases, runs accepted and
rejected native queries, compiles an explicit approximation subset, checks both compiled evidence
paths, visualizes the nested intervals, and solves the physical-coordinate link with CPU HiGHS.

Install the isolated notebook dependencies with `uv sync --group notebook`. The notebook is
offline, writes no evidence, and is explanatory rather than part of the canonical fixture
generation path.

## Validation

Run the feature's complete offline workflow from the OEL repository root:

```bash
uv run --locked --no-sync pytest \
  tests/unit/planning tests/unit/tpm \
  tests/integration/planning tests/integration/tpm \
  --ignore=tests/integration/tpm/test_mio_solver.py \
  --ignore=tests/integration/tpm/test_real_spflow_backend.py \
  --ignore=tests/integration/planning/test_gurobi_solver.py \
  --ignore=tests/integration/planning/test_spn_mio_gurobi.py

uv run --locked --no-sync python \
  examples/tpm_planning/run_declared_domains_pipeline.py --verify-fixture
```

The required path is offline and CPU-only after dependency installation. It exercises current
SPFlow, Pyomo, and HiGHS without a commercial solver, network access, notebook, or legacy checkout.
