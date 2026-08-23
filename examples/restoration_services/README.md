# French Restoration-Service Examples

This directory is the consumer surface for Feature 011. It demonstrates
explicit RTE acquisition, private fixture staging, deterministic offline aFRR
and mFRR replay, expected-result generation, and an offline-first notebook.
Reusable behavior belongs under `src/open_energy_lab`; these scripts only
validate arguments, hand credentials to explicit producer operations, and
present library results.

## Consumer Map

| Consumer | Network or secret | Responsibility |
|---|---|---|
| `fetch_rte_period.py` | Explicit RTE HTTPS operation; caller client ID/secret | Fetch or refresh one immutable RTE v5.2 restoration artifact |
| `stage_private_reference_data.py` | None; consumes explicitly acquired local artifacts | Validate the pinned periods and publish normalized restricted fixtures to fixed paths |
| `generate_reference_results.py` | None | Build labelled fixed-fraction scenarios, replay both products, settle them, and write deterministic expected results |
| `run_offline_replays.py` | None | Load validated fixtures and reproduce the two recorded demonstrations |
| `restoration_services_walkthrough.ipynb` | None by default; guarded explicit RTE/validated ENTSO-E branch | Explain source meaning, derivation, physical performance, degradation proxy, and settlement with plots |

Subsequent tasks implement these consumers. No script downloads on import,
fetches on cache miss, or silently chooses another source or period.

## Workflow Boundary

```text
explicit fetch/refresh
  -> ignored immutable artifact directory
  -> fixed private staging (normalized data only)
  -> explicit derived-scenario generation
  -> deterministic offline replay and settlement
  -> notebook/runner presentation
```

The default workflow starts at offline replay. It requires no credentials,
network, notebook runtime, solver, GPU, SLURM, W&B, or legacy checkout.

Live RTE operations read `RTE_CLIENT_ID` and `RTE_CLIENT_SECRET` only inside
the explicitly selected acquisition command. Optional ENTSO-E composition uses
only the existing validated Feature 010 `fr-day-ahead-symmetric-fcr-v1`
lifecycle and selects a compatible A44 `day_ahead_price` series by fingerprint.
Neither source is an automatic fallback for the other.

## Data Meaning

RTE aFRR and mFRR records are French control-area observations, not commands
sent to this simulated battery. A simulation input may be created only through
the recorded fixed-fraction mapping and must remain labelled
`derived_simulation` in artifacts, logs, tables, plots, and settlement. Prices,
satisfied need, and locally activated volume never authorize an inferred BESS
activation request.

## Storage and Output

- Live immutable artifacts stay beneath ignored `artifacts/restoration/`.
- Restricted reference fixtures stay beneath `tests/fixtures/restoration/`
  under `RESTRICTED_DATA.md` and explicit package exclusions.
- Raw market-response bodies and OAuth responses are not persisted.
- Notebook outputs and figure export are disabled in committed source.
- Temporary notebook figures, when explicitly enabled, stay beneath ignored
  `tmp/restoration-services-notebook/`.

The exact commands, selected periods, expected failures, optional notebook
runtime, and validation suites are maintained in
`specs/011-afrr-mfrr-services/quickstart.md` as implementation progresses.
