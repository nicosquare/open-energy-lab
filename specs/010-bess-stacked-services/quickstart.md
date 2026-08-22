# Quickstart: French BESS Stacked Services

This quickstart describes the implemented Feature 010 experimental-v1 surface. Routine review
is offline. A network and ENTSO-E token are needed only for an explicitly
selected fetch, refresh, or live compatibility check.

## Scope Of The Demonstration

- One France BESS
- Hourly fixed day-ahead baseline
- Six four-hour symmetric FCR commitments
- 15-minute state checkpoints
- 10-second activation replay
- Capacity-only FCR settlement plus an optional explicit research penalty
- No optimization, aFRR/mFRR, activation-energy settlement, or degradation cost

The selected real delivery day is 2022-08-19 in Europe/Paris:

```text
local [2022-08-19T00:00:00+02:00, 2022-08-20T00:00:00+02:00)
UTC   [2022-08-18T22:00:00Z,      2022-08-19T22:00:00Z)
```

## Environment

From the repository root:

```bash
uv sync
```

No additional solver, notebook, live service, or legacy environment is needed
for the offline workflow.

## Current Reference-Fixture Gate

The independent RTE activation gate passed and
`tests/fixtures/market/france_2022-08-19_activation_v1.json` is committed. The
earlier A81 HTTP 400 was traced to obsolete pre-R3 query assumptions. The
correct R3 profile uses A44 plus combined A81 (`B95/A52/A01`) containing both
reserve quantity and procurement price. Technical compatibility is validated
separately from redistribution. The current ENTSO-E CC BY 4.0 free-reuse list
does not include A44 day-ahead prices, and no Primary Owner permission was
supplied. The market and expected-replay fixtures therefore remain
intentionally absent even when a private local fetch succeeds. See the
[ENTSO-E Transparency Platform integration](../../docs/architecture/entsoe-transparency-platform.md)
and the authoritative gate record in `tests/fixtures/market/README.md`.

## Run The Recorded Offline Demonstration

```bash
uv run python examples/bess_stacked_services/run_offline_replay.py
```

This command is ready but currently fails closed with the recorded gate reason
and names the two missing fixtures. It becomes the default successful
demonstration only after the credentialed gate publishes both files.

The example loads:

```text
tests/fixtures/market/france_2022-08-19_market_v1.json
tests/fixtures/market/france_2022-08-19_activation_v1.json
tests/fixtures/market/france_2022-08-19_expected_replay_v1.json
```

It validates artifact and trace fingerprints, loads the documented fixed
stacked schedule, replays 8,640 samples without a transport, compares the trace
and totals with the expected-result fixture, and prints the settlement
breakdown. Repeated execution must produce the same result fingerprint.

The import-light implementation uses these public names:

```python
from open_energy_lab.market import (
    load_market_data_artifact,
    load_regulation_activation_trace,
)
from open_energy_lab.control import build_stacked_heuristic_baseline
from open_energy_lab.simulator import (
    StackedServiceReplayRequest,
    replay_stacked_services,
    settle_stacked_services,
)
```

## Run The Explicit Reference Benchmark

The initial reference host is Linux x86_64 on an Intel Xeon Gold 5218R CPU at
2.10 GHz, using one CPython 3.14.6 process with no deliberate parallelism and
at least 4 GiB available memory. On that host, run:

```bash
uv run pytest tests/integration/simulator/test_stacked_service_real_replay.py \
  -m reference_benchmark -q
```

The benchmark performs one warm-up followed by five measured artifact-load,
validation, replay, settlement, fingerprint, and comparison runs. Every
measured run must complete in under 10 seconds. Record the actual CPU,
allocation, memory, operating system, Python version, repository revision, and
five timings in `docs/migration/bess-stacked-services.md`. Results from other
hosts are informative until their relationship to the reference is documented.

The credentialed producer initially writes beneath ignored `artifacts/`. After
technical validation, explicitly stage the exact market artifact into this
private repository:

```bash
uv run python examples/bess_stacked_services/stage_private_reference_market.py \
  --market artifacts/market/reference-gate/MARKET_ARTIFACT.json \
  --destination tests/fixtures/market \
  --acknowledge-private-restricted-repository
```

This token-free operation requires an explicit private-repository
acknowledgement and records `repository_publication=prohibited`. It preserves
the normalized content fingerprint while changing the artifact fingerprint to
cover the restricted storage policy. Generate the expected replay from that
staged artifact:

```bash
uv run python examples/bess_stacked_services/generate_reference_replay.py \
  --market tests/fixtures/market/france_2022-08-19_market_v1.json \
  --destination tests/fixtures/market
```

The generator records the 475/540 EUR/MWh thresholds, every unmodified 5 kW
controller request, every admissible FCR-headroom interval, the fixed hourly
baseline, independently calculated settlement/throughput totals, input and
result fingerprints, and the same restricted-data policy. Unstaged A44 data
can write only beneath ignored `artifacts/`.

The three real-data fixtures are for authorized collaborators in this private
repository only. They are excluded from packages and releases and must not be
placed in public forks, mirrors, CI artifacts, or external stores. Remove them
before changing repository visibility. See
`docs/migration/restricted-reference-fixtures.md`.

## Verify The Manual Four-Hour Oracle

```bash
uv run pytest tests/integration/simulator/test_stacked_service_manual.py -q
```

The test independently verifies eight requested/delivered powers, nine stored
energy states, 2 kWh throughput, EUR 0.05 energy revenue, EUR 0.08 FCR revenue,
zero tracking error, and EUR 0.13 total profit.

## Run Routine Offline Checks

```bash
uv run pytest tests/unit/market tests/integration/market -m "not live_entsoe"
uv run pytest tests/unit/control tests/unit/simulator
uv run pytest tests/integration/control tests/integration/simulator -m "not reference_benchmark"
uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.market; import open_energy_lab.control; import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/market src/open_energy_lab/control/stacked_service.py src/open_energy_lab/simulator/stacked_service.py src/open_energy_lab/simulator/fcr_settlement.py tests/unit/market tests/unit/control tests/unit/simulator tests/integration/market tests/integration/control tests/integration/simulator
```

The routine group must complete without a token or network. The live and
reference-benchmark selections are excluded explicitly.

## Explicitly Fetch The Selected ENTSO-E Period

Obtain a valid token through the ENTSO-E Transparency Platform. Enter it
without placing the value in shell history:

```bash
read -rsp "ENTSO-E API token: " ENTSOE_API_TOKEN
printf "\n"
export ENTSOE_API_TOKEN
```

Then explicitly invoke acquisition:

```bash
uv run python examples/bess_stacked_services/fetch_french_period.py \
  --mode fetch \
  --start 2022-08-18T22:00:00Z \
  --end 2022-08-19T22:00:00Z \
  --destination artifacts/market \
  --env-file .env
```

Copy the committed `.env.example` to the Git-ignored `.env` file and replace
the placeholder, or export `ENTSOE_API_TOKEN` before invoking the command. The
optional dotenv reader is confined to this explicit acquisition consumer,
reads only `ENTSOE_API_TOKEN`, and never loads credentials during import,
artifact validation, or replay.

The script reads the dedicated environment variable only at the retrieval
boundary. It must not print the token or place it in a filename, manifest,
cache identity, or exception. Remove it from the shell after acquisition:

```bash
unset ENTSOE_API_TOKEN
```

A successful fetch prints a token-free artifact path and source/document
summary. It publishes locally only after A44 day-ahead price and both the
quantity and procurement-price measures in combined A81 validate for the
period. Do not commit the real output without the documented A44 reuse gate.

An acknowledgement, missing series, incompatible FCR product, gap, duplicate
conflict, wrong resolution/unit, or incomplete coverage fails and publishes no
artifact. Do not replace a failed series with RTE or synthetic values.

## Explicitly Refresh An Artifact

Set the token as above, then run:

```bash
uv run python examples/bess_stacked_services/fetch_french_period.py \
  --mode refresh \
  --start 2022-08-18T22:00:00Z \
  --end 2022-08-19T22:00:00Z \
  --current artifacts/market/MARKET_ARTIFACT.json \
  --destination artifacts/market
```

Replace `MARKET_ARTIFACT.json` with the fetch output. Refresh has exactly one
of these outcomes:

- `unchanged`: no new artifact
- `published`: new immutable artifact linked to the current fingerprint
- `revision_regression`: rejected; current artifact remains unchanged

Refresh never overwrites the current file.

## Explicitly Run The Live Compatibility Check

With the token set:

```bash
uv run pytest tests/integration/market/test_entsoe_live.py -m live_entsoe -q
```

This is a source-compatibility check, not the reproducibility gate. Network or
credential unavailability is documented separately and does not cause the
offline fixtures to be regenerated, skipped, or weakened.

The optional check asserts 24 A44 intervals and six aligned PT4H FCR volume and
price blocks sourced from the same A81 document. It scans diagnostics and
output files for the supplied token. Technical success does not authorize
committing the resulting A44 values.

On 2026-08-22 the corrected live check passed against the production R3 API in
40.43 seconds: two requests yielded 24 A44 intervals plus six aligned combined
A81 volume/price blocks. The token scan passed, and pytest's temporary output
was not retained as a repository fixture. The A44 redistribution gate remains
open.

## Explicitly Regenerate The Reference Activation Artifact

This optional provenance workflow requires a caller-supplied local copy of the
raw RTE file. It never downloads the file implicitly and is not part of routine
validation:

```bash
uv run python examples/bess_stacked_services/import_reference_activation.py \
  --input /path/to/RTE_Frequence_2022_08.txt \
  --expected-sha256 314a84556383161e9a9628b31eaa885e471f04db213a971c4f25efaef1053a8a \
  --source-revision 7e44738bb30e5c8204efe40103b9be4c2203685c \
  --start 2022-08-18T22:00:00Z \
  --end 2022-08-19T22:00:00Z \
  --created-at 2026-08-21T20:00:00Z \
  --destination artifacts/market
```

The consumer verifies the supplied digest, parses the selected raw observations
directly, applies explicit Europe/Paris left-hold intervals and
`clip((50-f)/0.2,-1,1)`, and writes a normalized activation artifact. It does
not execute the reference notebook's gap filling or duplicate removal. Routine
tests validate the committed normalized artifact without reopening this raw
file.

## Inspect Committed Activation Provenance Without A Token

```python
from pathlib import Path

from open_energy_lab.market import load_regulation_activation_trace

artifact = load_regulation_activation_trace(
    Path("tests/fixtures/market/france_2022-08-19_activation_v1.json")
)

print(artifact.artifact_fingerprint)
print(artifact.source["revision"], artifact.source["sha256"])
print(artifact.resolution, len(artifact.samples))
```

Loading either canonical artifact has no network-capable argument and does not read
`ENTSOE_API_TOKEN`.

## Compatibility Checks

```bash
uv run pytest tests/integration/simulator/test_stacked_service_compatibility.py -q
```

This verifies:

- zero FCR reproduces existing arbitrage power, SOC, throughput, and settlement
- zero energy baseline supports nonzero regulation and zero energy revenue
- regulation-only starts at the efficiency-aware centered SOC
- stacked schedules preserve both power-headroom directions
- future activation changes do not alter deterministic schedule construction
- terminal SOC target is report-only

## Expected Failure Behavior

The library fails before normal replay for missing or invalid artifact data,
partial energy/FCR product blocks, activation gaps/duplicates/range errors,
ambiguous timezone, non-integer grid mapping, missing price/volume blocks, or
invalid reserve headroom. An explicitly selected diagnostic replay can expose
power or SOC saturation but is marked as having failed commitment validation.

No workflow silently fills, interpolates, trims, prorates, fetches, or chooses
an alternative source.
