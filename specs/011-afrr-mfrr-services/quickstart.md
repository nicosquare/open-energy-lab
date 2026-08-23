# Quickstart: BESS aFRR and mFRR Services

This quickstart defines the expected user workflow after Feature 011 is
implemented. Offline replay is the default. Live retrieval is optional,
credentialed, and never required to use the recorded examples.

## What the Demonstration Shows

- RTE area-level aFRR and mFRR observations with exact source provenance
- an explicit fixed-fraction mapping into labelled simulated BESS inputs
- separate aFRR automatic trajectories and mFRR scheduled/direct events
- fixed directional commitments and a zero/no-lookahead energy baseline
- requested versus delivered power, SOC, upward/downward headroom, ramp,
  tracking/event performance, non-delivery, throughput, degradation proxy, and
  settlement
- why public control-area records are not individual battery commands

The recorded real demonstrations use:

- aFRR: `[2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)` with four PT15M RTE rows
- mFRR: `[2026-08-15T10:15:00Z, 2026-08-15T10:30:00Z)` with one downward SA
  row containing requested and satisfied volume
- fixed asset-allocation fraction `0.001`

All resulting activation inputs are simulations derived from area aggregates.

## Environment

Core offline use:

```bash
uv sync --group dev
```

Notebook use:

```bash
uv sync --group dev --group notebook
```

No credential, solver, GPU, SLURM, W&B, legacy runtime, or network is needed
for offline artifacts and replay.

## Run Both Offline Demonstrations

```bash
uv run python examples/restoration_services/run_offline_replays.py
```

Expected behavior:

- loads versioned artifacts from `tests/fixtures/restoration/`
- performs no environment or network access
- verifies source, derived mapping, replay, settlement, and expected-result
  fingerprints
- reports aFRR and mFRR separately
- labels RTE price use as an area-price scenario proxy
- does not expose FCR or the unselected restoration product as zero fields

## Inspect the Reference Inputs

```bash
uv run python -c "from pathlib import Path; from open_energy_lab.market.restoration_artifact import load_restoration_market_artifact; p=Path('tests/fixtures/restoration/france_2026-08-20_afrr_market_v1.json'); a=load_restoration_market_artifact(p); print(a.source, a.profile_id, a.covered_period, a.artifact_fingerprint)"
```

The loader validates locally and must not authenticate, read `.env`, or open a
socket.

## Open the Working Notebook

JupyterLab is the optional interactive interface:

```bash
uv run --group notebook jupyter lab examples/restoration_services/restoration_services_walkthrough.ipynb
```

The automated offline execution check uses `nbclient` from the same optional
group:

```bash
uv run --group notebook pytest tests/integration/simulator/test_restoration_notebook_execution.py -q
```

The notebook executes offline sections from top to bottom and includes plots or
tables for:

- source market fields and provenance
- commitments and fixed allocation mapping
- aFRR/mFRR request and delivered BESS power
- SOC and directional power/energy headroom
- aFRR tracking and mFRR event timing
- non-performance and causes
- charge/discharge/net energy and throughput
- degradation proxy
- capacity, activated-energy, penalty, gross, and net settlement

Saved source has empty outputs and `RUN_LIVE_QUERY = False`. Figure export is
off by default and may target only an ignored local output directory.

## Verify the Synthetic Oracles

```bash
uv run pytest tests/integration/simulator/test_afrr_restoration_manual.py -q
uv run pytest tests/integration/simulator/test_mfrr_restoration_manual.py -q
uv run pytest tests/integration/simulator/test_restoration_settlement_manual.py -q
```

The first two cases independently prove physical replay in both directions,
including zero activation, ramp/timing, capacity, headroom, power, SOC, and
overlap rejection. The third independently proves settlement, penalties, and
degradation. Together they remain within absolute tolerance `1e-6`.

## Routine Offline Validation

```bash
uv run pytest tests/unit/market tests/integration/market -m "not live_entsoe and not live_rte"
uv run pytest tests/unit/control tests/unit/simulator
uv run pytest tests/integration/control tests/integration/simulator -m "not reference_benchmark"
uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py tests/unit/test_migration_policy_docs.py
uv run python -c "import open_energy_lab; import open_energy_lab.market; import open_energy_lab.control; import open_energy_lab.simulator"
```

Routine validation must pass with credential variables unset and sockets
blocked.

## Feature 010 Compatibility Gate

```bash
uv run pytest tests/unit/control/test_stacked_service.py tests/unit/simulator/test_stacked_service.py tests/unit/simulator/test_fcr_settlement.py tests/unit/simulator/test_stacked_services_notebook.py tests/integration/simulator/test_stacked_service_manual.py tests/integration/simulator/test_stacked_service_compatibility.py tests/integration/simulator/test_reference_replay_generation.py tests/integration/simulator/test_stacked_service_real_replay.py -m "not reference_benchmark" -q
```

Existing FCR fixture bytes and reference results must remain unchanged.

## Explicit Live RTE Fetch

Copy the safe variable-name template and place values only in ignored `.env`:

```bash
cp .env.example .env
```

Never commit `.env`. Exported environment values take precedence over the
strict example-side loader.

Fetch the selected aFRR hour:

```bash
uv run python examples/restoration_services/fetch_rte_period.py \
  --resource standard_afrr_data \
  --start-utc 2026-08-20T00:00:00Z \
  --end-utc 2026-08-20T01:00:00Z \
  --output-dir .artifacts/restoration
```

Fetch the selected mFRR quarter:

```bash
uv run python examples/restoration_services/fetch_rte_period.py \
  --resource standard_mfrr_data \
  --start-utc 2026-08-15T10:15:00Z \
  --end-utc 2026-08-15T10:30:00Z \
  --output-dir .artifacts/restoration
```

The operation obtains a short-lived token at runtime. The request description,
console output, filenames, artifact, and raw digest evidence contain no client
credential or token. Raw response bodies are not persisted by default.

## Explicit Refresh

```bash
uv run python examples/restoration_services/fetch_rte_period.py \
  --resource standard_afrr_data \
  --start-utc 2026-08-20T00:00:00Z \
  --end-utc 2026-08-20T01:00:00Z \
  --refresh-from .artifacts/restoration/CURRENT_ARTIFACT.json \
  --output-dir .artifacts/restoration
```

Unchanged normalized content writes no file. Changed valid content creates one
predecessor-linked immutable successor. Failures leave the current artifact
untouched.

## Optional Live Compatibility Check

```bash
uv run pytest tests/integration/market/test_rte_live.py -m live_rte -q
```

This is an explicit source-compatibility check, not routine correctness
validation. It skips with a clear message when credentials are unavailable.

## Restricted Reference Staging

Only authorized collaborators may run:

```bash
uv run python examples/restoration_services/stage_private_reference_data.py \
  --afrr-artifact .artifacts/restoration/AFRR_ARTIFACT.json \
  --mfrr-artifact .artifacts/restoration/MFRR_ARTIFACT.json
```

The script verifies exact profiles, periods, fields, fresh SHA-256 response
digests, secret sentinels, and restricted-policy metadata before writing the
fixed repository fixture paths. Planning-time digests are comparison evidence:
a difference is reported for semantic review but is not, by itself, a staging
failure. Raw bodies are never persisted. The script refuses any public,
package, release, mirror, CI-artifact, or external store target.

The fixtures must be removed or relicensed before repository visibility changes
from private. Private repository access does not grant redistribution rights.

## Optional ENTSO-E Composition

ENTSO-E remains complementary, and Feature 011 introduces no new restoration
profile in its first release. The supported composition reuses a
time-compatible artifact from the existing Feature 010
`fr-day-ahead-symmetric-fcr-v1` fetch/refresh/offline lifecycle and selects only
its A44 `day_ahead_price` series by fingerprint in a
`RestorationStudyBundle`. If the caller's period is incompatible or no such
artifact is selected, the optional notebook branch reports that condition and
does not query or substitute another series. Never copy/join observations into
one acquisition artifact or treat ENTSO-E as an automatic RTE fallback.

## Expected Failure Behavior

Operations fail with source, resource/field, requested period, observed
sanitized condition, and expected contract for authentication, transport,
coverage, resolution, unit, duplicate/conflict, null required field, wrong
product/direction, ambiguous aFRR opposing need, mapping capacity excess, aFRR
gap, mFRR overlap, artifact integrity, or restricted-distribution failure.

If physical inputs are valid but a declared required price is missing or
ambiguous, replay remains available and settlement/total are unavailable. No
price or missing component is silently replaced with zero.
