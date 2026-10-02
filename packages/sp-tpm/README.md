# sp-tpm

Tractable probabilistic models for stochastic programming: fit SPFlow
circuits, query them, and compile them into Pyomo or Gurobi optimization
models (chance constraints, conditional-probability embeddings).

Installed as `sp-tpm`, imported as `tpm`:

```python
import tpm
artifact = tpm.fit_tpm_artifact_from_rows(rows, build_request=request)
```

Developed inside the Open Energy Lab repository (`packages/sp-tpm`) and
used by its `planning` package; it must not import `open_energy_lab`.
Python >= 3.11. Extras: `pyomo`, `highs`, `gurobi`.
