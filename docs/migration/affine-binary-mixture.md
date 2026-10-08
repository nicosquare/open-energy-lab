# Binary product-mixture learning and conditional attachments

The paired SAA–TPM experiments in `tpm_for_sp` now use OEL for their reusable
Bernoulli/Gaussian product-mixture mathematics, strengthened binary PWL
conditional compiler, optional Gurobi attachment and solver-independent cuts.
The campaign remains responsible for data, normalization, training schedules,
checkpoint selection, business objectives and thresholds, solver budgets,
callbacks, persistence and experiment assessment.

## Library interfaces

- `tpm.native` (the former `product_mixture` merged in, B5d): the mixture is a
  genuine SPFlow `Sum(Product(leaves))` built by `build_native_mixture` or
  `initialize_native_mixture`; its leaves hold every parameter. Training and
  batch queries use `native_mixture_log_likelihood`, a closed form that reads
  those leaves (NaN marginalizes a column) and is about 10x faster than SPFlow's
  `log_likelihood`; `check_native_mixture_against_spflow` verifies agreement.
  `native_mixture_parameters` exports the logits, locations and log-scales the
  affine encoders take.
- `tpm.affine`: `compile_affine_logsum`,
  `compile_binary_mixture_log_ratio`, `evaluate_affine_logsum`,
  `evaluate_binary_log_ratio`, `conditional_affine_bounds`, and
  `validate_affine_logsum`. JSON-compatible records preserve both the original
  PWL grid and its clipped restrictions. Full evaluation supplies interpolation,
  maximum-selector and disaggregation assignments. Both conditional queries
  use the fitted mixture and share the same decision dimension.
- `tpm.affine_gurobi`: `attach_affine_log_ratio` and
  `check_affine_sos_assignments`. An attachment accepts distinct caller-owned
  binary variables and an optional namespace, validates the graph before adding
  variables, and returns numerator, denominator and log-ratio roots plus the
  variable mapping. It preserves the caller's objective and solver settings.
  Thresholds, starts, optimization and model/environment disposal are the
  caller's responsibility. Multiple attachments share business variables.
- `open_energy_lab.tpm.binary_cuts`: `CompiledProbabilitySeparator` and
  `ConditionalFaceCertifier`. These evaluate compiled probabilities and certify
  excluded binary points or faces. The caller supplies the log-probability
  threshold and owns solver callbacks and post-search validation.

For example, after fitting parameters `(binary, mixture, location, log_scale,
event)`, compile and attach a conditional event-zero probability:

```python
import math
from open_energy_lab.tpm.affine import compile_binary_mixture_log_ratio
from open_energy_lab.tpm.affine_gurobi import attach_affine_log_ratio

records = compile_binary_mixture_log_ratio(
    binary.detach().cpu().numpy(),
    mixture.detach().cpu().numpy(),
    event.detach().cpu().numpy(),
    event_value=0,
    breakpoint_count=9,
)
attachment = attach_affine_log_ratio(model, decisions, records, namespace="success")
model.addConstr(attachment.root >= math.log(0.9))
```

This specialized compiler supports binary decisions and at least two mixture
components. It retains the validated guarded exponential domain `[-500, 0]`
and rejects terms outside that domain instead of silently changing the curve.
It approximates log probabilities; it does not promise exact analytical
feasibility. The existing general conditional-circuit/Pyomo/HiGHS APIs remain
available. Importing these new modules does not load Torch, SPFlow or a solver;
those dependencies are loaded only by the operations that require them.

## Provenance and verification

The extracted behavior comes from these exact `tpm_for_sp` paths:

- `src/tpm_for_sp/knapsack_tpm/filtered/model.py`: vectorized joint likelihood,
  row-center initialization and SPFlow materialization.
- `src/tpm_for_sp/knapsack_tpm/filtered/encoding.py` and `filtered/bounds.py`:
  affine log-sum records, curve-preserving clipping and shared-decision bounds.
- `src/tpm_for_sp/knapsack_tpm/filtered/sos2.py` and
  `src/tpm_for_sp/knapsack_tpm/compilation.py`: SOS2, maximum disaggregation,
  winner links and conditional bounds.
- `src/tpm_for_sp/knapsack_tpm/decision_separation.py` and
  `src/tpm_for_sp/knapsack_tpm/conditional_cuts.py`: point exclusion and
  interval-certified binary face exclusion.

The old experiment implementations remain as parity references. OEL tests use
non-knapsack dimensions and feature orders, compare all likelihood gradients
with current SPFlow, enumerate binary assignments to check bounds/certificates,
round-trip compilation records through JSON, and check lazy imports. Optional
Gurobi tests verify complete assignments, shared decisions, namespace isolation,
caller ownership and malformed-graph rejection. The experiment suite also
compares OEL against the preserved development formulation across all 1,024
knapsack decisions, including variable/constraint/SOS counts and bounds.

```bash
pytest tests/unit/tpm/test_native_closed_form.py tests/unit/tpm/test_affine.py
# Explicit licensed integration check:
pytest tests/integration/tpm/test_affine_gurobi.py
```

## Working source and experiment snapshots

OEL's working checkout is the maintained implementation. New campaigns freeze
its current Python sources alongside the experiment sources and use those
snapshots for every worker. Saved hashes identify the exact implementation,
including uncommitted changes. Restart verifies those snapshots; presentation
reads evidence without importing OEL or comparing the current checkout.
Improving OEL therefore affects new campaigns without changing completed ones.

When developing directly from the source tree, use `PYTHONPATH=src` from OEL's
root (its pytest configuration already does this). The experiment's tests add
`references/oel/src` to their import path. An existing installed wheel is not
automatically updated by editing the checkout; intentionally refresh that
installation when needed. Campaign workers use the frozen source explicitly,
so they cannot silently fall back to an older installed wheel.
