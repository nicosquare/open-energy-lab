# Restoration-Service Fixtures

This directory is the offline evidence boundary for Feature 011, French BESS
aFRR and mFRR services. Reusable acquisition, validation, mapping, replay, and
settlement behavior belongs under `src/open_energy_lab`; tests and examples
consume only explicit, versioned artifacts from this directory.

## Layout

```text
restoration/
├── README.md
├── RESTRICTED_DATA.md
├── synthetic_rte/                         # authored RTE JSON parser inputs
├── manual_afrr_v1.json                    # authored arithmetic oracle
├── manual_mfrr_v1.json                    # authored arithmetic oracle
├── france_2026-08-20_afrr_market_v1.json  # restricted normalized source data
├── france_2026-08-20_afrr_scenario_v1.json
├── france_2026-08-15_mfrr_market_v1.json  # restricted normalized source data
├── france_2026-08-15_mfrr_scenario_v1.json
└── france_restoration_expected_results_v1.json
```

Files are added by their owning implementation tasks. A missing restricted
artifact is never downloaded or synthesized on cache miss.

## Authored Fixtures

`synthetic_rte/` and the two `manual_*` files are project-authored test inputs.
They contain no production response body or caller data and may be distributed
with the repository under its normal license. Each authored fixture must state:

- the parser, equation, or failure path it validates;
- its generation method or that it was written by hand;
- exact input periods, units, directions, and expected invariants;
- the default absolute tolerance when numeric results are involved; and
- that it is synthetic and is not evidence of an operational BESS command.

Synthetic cases preserve source-null, field-absent, and numeric-zero states as
different values. They may imitate the documented RTE JSON shape but must never
be described as a captured production response.

The authored `synthetic_rte/` matrix contains successful aFRR and mFRR shapes
plus malformed-root, empty, null/missing/zero, gap, overlap, conflicting
duplicate, wrong-resolution, wrong-direction, wrong-unit, oversized,
authentication, rate-limit, transient, and permanent response cases. The four
aFRR requested-need values and one mFRR SA requested-volume value reproduce the
documented hand-checkable scenario inputs; all response bytes remain authored
and are not production captures.

`manual_afrr_v1.json` is a project-authored arithmetic oracle for Feature 011
User Story 2. Its six deterministic cases separately publish nominal upward,
downward, and zero tracking; ramp saturation; charge-power saturation;
maximum-SOC/energy saturation; reserved downward-headroom saturation; and
zero-activation baseline preservation. Every input is synthetic, every power
value is an interval average under the charge-positive convention, and every
expected terminal or activation energy is direct `kW * interval-hours`
integration with absolute tolerance `1e-6`. The fixture is maintained by hand
and changes only with a versioned activation, battery, or replay equation.

`manual_mfrr_v1.json` is the corresponding project-authored event oracle for
User Story 3. It publishes a rectangular upward scheduled activation, a
downward direct activation with explicit delay and linear ramps, an empty
zero-activation horizon, and one invalid scheduled/direct overlap. Requested
event energy follows `power * (hold + 0.5*ramp_up + 0.5*ramp_down) / 3600`;
native-grid interval averages conserve that analytic result within `1e-6`.
The values are synthetic and are not evidence of an RTE-to-asset activation
order. The fixture changes only with a versioned event-shape, overlap, battery,
or replay equation.

## Restricted Fixtures

Every `france_*` file listed in `RESTRICTED_DATA.md` is derived from real market
observations and is restricted to authorized collaborators in the confirmed
private repository. That policy covers normalized source artifacts, derived
scenarios, and expected results because downstream values can reproduce the
restricted observations.

Restricted fixtures must be excluded from wheels, source distributions,
releases, public CI artifacts, public forks or mirrors, and external artifact
stores. They must be removed or reassessed before any repository visibility
change. Private repository access is not permission to redistribute them.

## Credentials and Raw Responses

No client ID, client secret, access token, Basic/Bearer header, credential-
bearing URL, OAuth response, or local `.env` value may appear in a fixture,
filename, digest input, log, exception, notebook output, or documentation
example. Routine tests use conspicuous sentinels and require zero occurrences.

Production market-response bodies are digest-only by default. A raw response
may be retained only as a separately verified restricted sidecar when source
terms and project policy explicitly allow it. OAuth responses are never raw
market evidence and are never retained or fingerprinted.

## Provenance Template

Each fixture record must provide:

```text
Fixture path:
Purpose:
Origin and owner:
Source API/profile/version or authored contract:
Requested and covered UTC period:
Resolution, units, and directions:
Generation command:
Input artifacts and fingerprints:
Expected invariant and tolerance:
Transformation history:
Raw-response digest/retention status:
License, access, and redistribution policy:
Refresh policy:
```

Real artifacts are refreshed only through an explicit credentialed acquisition
followed by the fixed private-staging workflow. An upstream response-digest
change is reported for semantic review and is not, by itself, permission to
overwrite an existing immutable fixture.

## Current Restricted Fixture Records

All five records below share this access policy: authorized collaborators in
the owner-confirmed private repository only; not licensed under Apache-2.0;
prohibited from packages, releases, public CI artifacts, public forks/mirrors,
and external artifact stores; remove or reassess before a visibility change.
Source attribution is **RTE Balancing Energy API v5.2; normalized by Open Energy
Lab**. Numeric replay comparisons use absolute tolerance `1e-6`.

### `france_2026-08-20_afrr_market_v1.json`

```text
Fixture path: tests/fixtures/restoration/france_2026-08-20_afrr_market_v1.json
Purpose: normalized one-hour RTE aFRR market-area reference
Origin and owner: production RTE Balancing Energy; RTE Réseau de Transport d'Électricité
Source API/profile/version: standard_afrr_data; fr-rte-balancing-energy-v5.2-afrr-v1; catalog 5.2/path v5
Requested and covered UTC period: [2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)
Resolution, units, and directions: four PT15M rows; MW and EUR/MWh; separate upward/downward series
Generation command: explicit fetch_rte_period.py FETCH, then stage_private_reference_data.py with private acknowledgement
Input artifact fingerprint: 83f0c88e5c8d9c0f781305a9552596c3a03956588a75871e9f78e97415811516
Content fingerprint: 9f44272301f164562d7552723054438253704c3f65618d2acf8e70755ffd1506
File SHA-256: 5042f7d7d21ec839670b80b22eaa1abcbed2eacb0bc2d1d55367bbd543723799
Expected invariant: upward requested need is 425,315,290,345 MW chronologically; downward requested need is zero; all eight exact source series are retained
Transformation history: explicit-offset timestamps normalized to UTC; rows ordered chronologically with source_row retained; no value/unit rescaling
Raw-response digest/retention: d2496d713c7f217ff76487db2aba0b7a49479861118bea61ca3c001fbbfe2eb3; DIGEST_ONLY; no sidecar
Retrieval time: 2026-08-23T09:02:18.482403Z
Refresh policy: reacquire explicitly; validate exact semantics; report digest drift; never overwrite immutable bytes
```

### `france_2026-08-15_mfrr_market_v1.json`

```text
Fixture path: tests/fixtures/restoration/france_2026-08-15_mfrr_market_v1.json
Purpose: normalized one-quarter RTE mFRR market-area reference with scheduled activation evidence
Origin and owner: production RTE Balancing Energy; RTE Réseau de Transport d'Électricité
Source API/profile/version: standard_mfrr_data; fr-rte-balancing-energy-v5.2-mfrr-v1; catalog 5.2/path v5
Requested and covered UTC period: [2026-08-15T10:15:00Z, 2026-08-15T10:30:00Z)
Resolution, units, and directions: two directional PT15M rows; MW and EUR/MWh; SA/DA and upward/downward retained separately
Generation command: explicit fetch_rte_period.py FETCH, then stage_private_reference_data.py with private acknowledgement
Input artifact fingerprint: d2d4007fafe5138f0bfdc8d91ba232c435f9b4f7097a0cc519064011c624ca10
Content fingerprint: 57bff8041d4691e7cda82da53790b92228130007c2d2ba5986fc280e5f14c1a4
File SHA-256: 76c5ad31f677a83b7a70d7bb629a4bfa9636b66d2a065302750fdfb8039cec91
Expected invariant: downward SA requested=357 MW, satisfied=300 MW, clearing=64.83 EUR/MWh; upward volumes and DA remain source-null; no DA event is inferred
Transformation history: explicit-offset timestamps normalized to UTC; rows ordered chronologically with direction/source_row retained; null/absent/zero remain distinct
Raw-response digest/retention: ce9d3c3d694a78776e5bdb188239f9b2ed4b711e3c389d0e89c8a47e5391d1a1; DIGEST_ONLY; no sidecar
Retrieval time: 2026-08-23T09:06:41.082659Z
Refresh policy: reacquire explicitly; validate exact semantics; report digest drift; never overwrite immutable bytes
```

The reproducible acquisition and staging commands are:

```bash
uv run python examples/restoration_services/fetch_rte_period.py \
  --resource standard_afrr_data \
  --start-utc 2026-08-20T00:00:00Z \
  --end-utc 2026-08-20T01:00:00Z \
  --output-dir artifacts/restoration/reference-acquisition/afrr \
  --env-file .env

uv run python examples/restoration_services/fetch_rte_period.py \
  --resource standard_mfrr_data \
  --start-utc 2026-08-15T10:15:00Z \
  --end-utc 2026-08-15T10:30:00Z \
  --output-dir artifacts/restoration/reference-acquisition/mfrr \
  --env-file .env

uv run python examples/restoration_services/stage_private_reference_data.py \
  --afrr-artifact artifacts/restoration/reference-acquisition/afrr/ARTIFACT.json \
  --mfrr-artifact artifacts/restoration/reference-acquisition/mfrr/ARTIFACT.json \
  --acknowledge-private-restricted-repository
```

`ARTIFACT.json` means the immutable path printed by each fetch operation; no
cache-miss lookup or wildcard selection is performed by the staging command.

### `france_2026-08-20_afrr_scenario_v1.json`

```text
Fixture path: tests/fixtures/restoration/france_2026-08-20_afrr_scenario_v1.json
Purpose: derived-simulation aFRR activation, commitment, battery, capability, lineage, and settlement assumptions
Origin and owner: deterministic Open Energy Lab derivation from the restricted RTE aFRR artifact
Source contract: oel.restoration.reference-scenario.v1 / fr-restoration-reference-v1
Requested and covered UTC period: [2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)
Resolution, units, and directions: four PT15M signed interval-average kW requests; upward is negative/discharge
Generation command: generate_reference_results.py with private acknowledgement
Input market artifact: 83f0c88e5c8d9c0f781305a9552596c3a03956588a75871e9f78e97415811516
Mapping fingerprint: d1fc944a2f45e1032f7c9c6cafc76b212fd6d4b54576ae1eb58adbe0853a5178
Scenario fingerprint: fea97fb2e9596e907a7204df9466c355d0ce2493c8c846e85a69093eadcfd9cb
File SHA-256: b21a9bd4f56fe6fe324ce0e4c93b566b525102f404925301b877f12a8ef9a62c
Expected invariant: fixed 0.001 mapping yields -425,-315,-290,-345 kW without interpolation, upsampling, normalization, or clipping
Transformation history: MW * 1000 * 0.001; explicit sign convention; derived_simulation label; comparison series retained by fingerprint
Raw-response digest/retention: inherited only through market-artifact fingerprint; no raw body in scenario
Refresh policy: regenerate only after reviewed immutable market/scenario version change; identical inputs must reproduce identical bytes
```

### `france_2026-08-15_mfrr_scenario_v1.json`

```text
Fixture path: tests/fixtures/restoration/france_2026-08-15_mfrr_scenario_v1.json
Purpose: derived-simulation mFRR scheduled event, commitment, battery, capability, lineage, and settlement assumptions
Origin and owner: deterministic Open Energy Lab derivation from the restricted RTE mFRR artifact
Source contract: oel.restoration.reference-scenario.v1 / fr-restoration-reference-v1
Requested and covered UTC period: [2026-08-15T10:15:00Z, 2026-08-15T10:30:00Z)
Resolution, units, and directions: one 900-second downward/charge SCHEDULED event at 357 kW; DA source-null
Generation command: generate_reference_results.py with private acknowledgement
Input market artifact: d2d4007fafe5138f0bfdc8d91ba232c435f9b4f7097a0cc519064011c624ca10
Mapping fingerprint: 24275dcf84e098521315995a2c2cda63cf46257ff46c91325ac5cfaadba52f0b
Scenario fingerprint: 028b0067c9173c4998d47616d138e395f682f676e1a9d012a1e32769cee6a172
File SHA-256: 8881bb013e8649c8dc86c5c73848dea8611cbce2146c12ced5b6940163169489
Expected invariant: fixed 0.001 mapping yields one rectangular SA event with 89.25 kWh requested energy; no DA event is fabricated
Transformation history: MW * 1000 * 0.001; explicit rectangular-event assumption (0 delay/ramp, 900-second hold); derived_simulation label
Raw-response digest/retention: inherited only through market-artifact fingerprint; no raw body in scenario
Refresh policy: regenerate only after reviewed immutable market/scenario version change; identical inputs must reproduce identical bytes
```

### `france_restoration_expected_results_v1.json`

```text
Fixture path: tests/fixtures/restoration/france_restoration_expected_results_v1.json
Purpose: complete deterministic physical replay and explicit scenario-proxy settlement oracle for both real demonstrations
Origin and owner: Open Energy Lab offline generator from the two restricted scenarios
Source contract: oel.restoration.reference-results.v1 / fr-restoration-reference-v1
Periods: exact aFRR hour and mFRR quarter recorded above
Generation command: generate_reference_results.py with private acknowledgement
Input scenario fingerprints: fea97fb2e9596e907a7204df9466c355d0ce2493c8c846e85a69093eadcfd9cb; 028b0067c9173c4998d47616d138e395f682f676e1a9d012a1e32769cee6a172
Result-set fingerprint: abe68d7130db368245ca41d972dd41ec5a544ba4ef25d208c93377b3e440586f
Notebook-display fingerprint: 88ab88e3859e4fe81555651468bcc9e4c474db43feee11ecd1eef6b18568e976
File SHA-256: 277a3d7c429bc108e42a5ed659d7d954ccc67c30c7d7e67e90083e381044e135
Expected aFRR invariant: 343.75 kWh requested=delivered, zero undelivered, terminal SOC 0.3190789473684211, gross EUR 59.2551625, degradation EUR 6.875, net EUR 52.3801625
Expected mFRR invariant: 89.25 kWh requested=delivered, zero undelivered, terminal SOC 0.54239375, gross EUR 5.7860775, degradation EUR 1.785, net EUR 4.0010775
Transformation history: deterministic replay; delivered-energy settlement; area prices labelled scenario_proxy; unconfigured penalty; 0.02 EUR/kWh throughput comparison proxy
Raw-response digest/retention: no raw body; input market identities and digest-only provenance remain referenced
Refresh policy: generator must reproduce byte-identical output for unchanged inputs; review every upstream identity or semantic version change
```

Generate all three derivative files atomically from the fixed staged market
fixtures:

```bash
uv run python examples/restoration_services/generate_reference_results.py \
  --acknowledge-private-restricted-repository
```
