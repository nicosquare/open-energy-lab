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

No script downloads on import, fetches on cache miss, or silently chooses
another source or period.

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

Run the complete offline audit:

```bash
uv run python examples/restoration_services/run_offline_replays.py
```

It must reproduce result-set fingerprint
`abe68d7130db368245ca41d972dd41ec5a544ba4ef25d208c93377b3e440586f`
and notebook-display fingerprint
`88ab88e3859e4fe81555651468bcc9e4c474db43feee11ecd1eef6b18568e976`.

Run the synthetic physical/settlement oracles and the restricted zero-network
real-data replay separately:

```bash
uv run pytest tests/integration/simulator/test_afrr_restoration_manual.py -q
uv run pytest tests/integration/simulator/test_mfrr_restoration_manual.py -q
uv run pytest tests/integration/simulator/test_restoration_settlement_manual.py -q
uv run pytest tests/integration/simulator/test_restoration_real_replays.py -q
```

The first three commands prove hand-calculable product behavior. The final
command reloads only the fixed private normalized artifacts and reproduces both
recorded scenario, replay, settlement, and fingerprint contracts without a
credential or socket.

Install the optional notebook group and either open the source interactively or
execute its offline acceptance test:

```bash
uv sync --group dev --group notebook
uv run --group notebook jupyter lab \
  examples/restoration_services/restoration_services_walkthrough.ipynb
uv run --group notebook pytest \
  tests/integration/simulator/test_restoration_notebook_execution.py -q
```

The execution test inserts network and credential-read guards into an in-memory
copy, executes every offline cell in order, validates all tables/figures and
both fingerprints, and leaves the source notebook unchanged with empty outputs.

Live RTE operations read `RTE_CLIENT_ID` and `RTE_CLIENT_SECRET` only inside
the explicitly selected acquisition command. Optional ENTSO-E composition uses
only the existing validated Feature 010 `fr-day-ahead-symmetric-fcr-v1`
lifecycle and selects a compatible A44 `day_ahead_price` series by fingerprint.
Neither source is an automatic fallback for the other.

An explicit RTE fetch or refresh uses the ignored `artifacts/` tree:

```bash
uv run python examples/restoration_services/fetch_rte_period.py \
  --resource standard_afrr_data \
  --start-utc 2026-08-20T00:00:00Z \
  --end-utc 2026-08-20T01:00:00Z \
  --output-dir artifacts/restoration/notebook-live-query \
  --env-file .env

uv run python examples/restoration_services/fetch_rte_period.py \
  --resource standard_afrr_data \
  --start-utc 2026-08-20T00:00:00Z \
  --end-utc 2026-08-20T01:00:00Z \
  --refresh-from artifacts/restoration/notebook-live-query/CURRENT.json \
  --output-dir artifacts/restoration/notebook-live-query \
  --env-file .env
```

For ENTSO-E, first use Feature 010's unchanged
`fetch_french_period.py` fetch/refresh lifecycle. The notebook accepts only the
resulting exact `fr-day-ahead-symmetric-fcr-v1` artifact when its A44
`day_ahead_price` covers the caller period, then reports the selected series
fingerprint. Otherwise it reports `no compatible profile was selected` and
does not query or substitute another profile.

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

The fixed private staging and deterministic derivative generation commands are:

```bash
uv run python examples/restoration_services/stage_private_reference_data.py \
  --afrr-artifact artifacts/restoration/reference-acquisition/afrr/ARTIFACT.json \
  --mfrr-artifact artifacts/restoration/reference-acquisition/mfrr/ARTIFACT.json \
  --acknowledge-private-restricted-repository

uv run python examples/restoration_services/generate_reference_results.py \
  --acknowledge-private-restricted-repository
```

Missing credentials, malformed/gapped source data, wrong product or direction,
ambiguous opposing aFRR need, mapping above commitment, overlapping mFRR events,
missing required settlement prices, restricted target paths, and fixture
identity drift all fail explicitly. Physical replay remains available when a
financial input alone is unavailable; no partial total is presented.

The full command matrix and expected failure behavior are maintained in
`specs/011-afrr-mfrr-services/quickstart.md`.
