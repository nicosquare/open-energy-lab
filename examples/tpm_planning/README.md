# TPM Planning Examples

This directory holds tracked replay scripts for the real TPM-planning backend
path. The scripts are kept in git so another machine can retake the work
without depending on ignored `tmp/` code, while their generated artifacts stay
under `tmp/` so example runs do not dirty the repository.

## What These Examples Cover

`run_real_backend_pipeline.py`

- reloads committed weather and demand fixtures
- evaluates one simulator family
- exports one planning dataset with canonical `shortfall`
- fits a TPM artifact with the derived binary event target
- queries `P(shortfall > threshold | decisions)` through the real backend when
  available
- assembles one `risk_evaluation_mode="spn_mip"` planning problem
- solves the resulting MIO with Pyomo plus Gurobi

`run_generic_rows_pipeline.py`

- fits a TPM artifact directly from arbitrary rows instead of simulator export
- queries the fitted artifact
- solves the direct SPN chance model from the artifact
- falls back to a demo adapter only when the real legacy-compatible SPFlow
  backend is unavailable

## Output Location

Both examples write generated artifacts to:

`tmp/open-energy-lab-pipeline-real-backends/`

Expected outputs include:

- `planning_dataset.json`
- `tpm_artifact.json`
- `tpm_artifact.spn_payload.pkl`
- `generic_rows_tpm_artifact.json`
- `generic_rows_tpm_artifact.spn_payload.pkl`
- `pipeline_summary.json`
- `generic_rows_pipeline_summary.json`

## Replay Commands

From the repository root:

```bash
uv run python examples/tpm_planning/run_real_backend_pipeline.py
uv run python examples/tpm_planning/run_generic_rows_pipeline.py
```

To inspect backend capability state first:

```bash
uv run python -c "from open_energy_lab.tpm import detect_spflow_backend_capabilities; import json; print(json.dumps(detect_spflow_backend_capabilities(), indent=2, sort_keys=True))"
```

## Success Criteria

For `run_real_backend_pipeline.py`, success means the generated
`pipeline_summary.json` reports:

- `query_result.source == "spflow_backend"`
- `risk_evaluation_mode == "spn_mip"`
- `solve_execution_mode == "native-pyomo-solver"`
- `solve_status == "optimal"`

For `run_generic_rows_pipeline.py`, success means the generated
`generic_rows_pipeline_summary.json` reports:

- `query_result.source == "spflow_backend"`
- `solve_execution_mode == "native-pyomo-solver"`
- `solve_status == "optimal"`

## Environment Actually Used On This Machine

The real-backend replay documented here was exercised on August 17, 2026 with:

- `spflow==0.0.41`
- `pyomo==6.10.1`
- `scikit-learn==1.9.0`
- `networkx==3.6.1`
- `scipy==1.17.1`
- `gurobipy==13.0.2`

The detected SPFlow capability state was:

- `installed_backend_module = "spn"`
- `legacy_api_module_prefix = "spn"`
- `supports_real_spn_training = true`
- `supports_real_spn_query = true`
- `supports_spn_mip_serialization = true`

## Results Observed Here

During the August 17, 2026 replay on this machine:

- the real simulator-backed example selected
  `{battery_capacity_kwh: 8.0, solar_capacity_kw: 4.0}`
- the real simulator-backed example reported `objective_value = 13400.0`
- the real simulator-backed example reported
  `estimated_shortfall_risk = 0.25`
- the generic-rows example solved successfully with the real backend path when
  the optional stack was installed

## Caveats

- These examples require optional dependencies that are not part of the
  minimal `pyproject.toml` runtime declaration yet.
- The solve step requires a working Gurobi installation and license.
- The TPM runtime path uses the legacy-compatible `spn.*` API layout and the
  compatibility shims in `open_energy_lab.tpm.optional_spflow`.
- Only `max` and `piecewise` SPN sum encodings are valid in the MIO path.
  `lower_tangent` is rejected by the current artifact metadata validation.
