# French BESS Stacked-Services Migration

## Status

Feature 010 owns the first library-native, fixed-schedule replay of French
day-ahead energy and symmetric FCR. Market acquisition, canonical artifacts,
activation artifacts, schedule construction, physical delivery, and settlement
remain separate boundaries. Routine use is deterministic, fixture-backed, and
offline.

The synthetic/manual replay path is implemented and validated. The independent
RTE activation gate passed for the selected delivery day. The earlier A81 HTTP
400 was caused by obsolete query assumptions and is superseded by the current
R3 A44/combined-A81 contract. Technical compatibility and publication rights
are recorded separately. A44 redistribution still lacks a documented basis
under the current ENTSO-E free-reuse list, so the market and expected-replay
fixtures remain absent, with no replacement data introduced. The authoritative gate record is in
`tests/fixtures/market/README.md`.

## Reference Evidence

The activation behavior was extracted from these exact external sources rather
than adding a runtime dependency:

- repository: `lauinger/robust-storage-bidding`
- commit: `7e44738bb30e5c8204efe40103b9be4c2203685c`
- source data: `data_processing/freq_data/RTE_Frequence_2022_08.txt`
- source transformation evidence: `data_processing/RTE_frequencies.ipynb`
- repository license: `LICENSE` at the pinned commit (MIT)
- raw-file SHA-256:
  `314a84556383161e9a9628b31eaa885e471f04db213a971c4f25efaef1053a8a`

The external repository and raw RTE file are not imported, opened, downloaded,
or executed by the library or routine tests. Regeneration is an explicit example
consumer that accepts a caller-supplied local file and verifies its complete
digest before parsing. The raw file is not committed.

RTE attribution is “Source: RTE Réseau de Transport d'Électricité.” The RTE
Services Portal General Terms of Service, Article 9, checked on 2026-08-21,
permits reuse of public data when the source is mentioned:
`https://www.services-rte.com/en/general-terms-and-conditions-of-use.html`.
ENTSO-E publishes a CC BY 4.0 open-data subset. The list checked on 2026-08-22
includes contracted reserve amount and price but not Article 12.1(d) day-ahead
prices. The Terms of Use place the pre-reuse check on the data user and direct
the user to seek the Primary Owner's agreement where rights may be prejudiced.
No such A44 permission was supplied, so the normalized market fixture is not
redistributed:
`https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions`
and
`https://transparencyplatform.zendesk.com/hc/article_attachments/40921869379729`.

## Credentialed ENTSO-E Gate

The 2026-08-22 run used the explicit producer with a token loaded from the
Git-ignored `.env` file. The token remained outside request values and did not
appear in output, exceptions, paths, manifests, or sidecars. A44 validated
after accepting the official response profile's absent process field and exact
`PT60M` hourly spelling while preserving canonical `PT1H` output semantics.

The original A81 request used obsolete `A34/A95` assumptions and returned HTTP
400. The official R3 Postman collection instead defines 17.1.B&C as
`A81/B95/A52/A01`. The corrected response is a ZIP containing a
`Balancing_MarketDocument` in namespace
`urn:iec62325.351:tc57wg16:451-6:balancingdocument:4:4`; each point carries
both `quantity` and `procurement_Price.amount`. A separate A89 request is not
part of R3. The exact request, response safeguards, and normalization formula
are documented in the
[ENTSO-E Transparency Platform integration](../architecture/entsoe-transparency-platform.md).
The corrected opt-in production gate passed on 2026-08-22 with 24 A44
intervals and six aligned PT4H volume/price blocks sourced from the same A81
document. Its token scan passed and its temporary artifact was not retained.
This resolves technical compatibility only; A44 redistribution remains the
reason the committed market and expected-replay fixtures are absent.
ENTSO-E's archive notice records that legacy R2 data items were discontinued on
11 December 2025:
`https://transparencyplatform.zendesk.com/hc/en-us/articles/41986091964305-Archives-for-legacy-Transparency-Platform-publications`.

## Canonical Activation

The selected local day and UTC replay period are:

```text
Europe/Paris [2022-08-19T00:00:00+02:00, 2022-08-20T00:00:00+02:00)
UTC          [2022-08-18T22:00:00Z,      2022-08-19T22:00:00Z)
```

Direct import proved 8,640 unique observations on an exact 10-second grid,
with no gap or notebook repair and a frequency range of 49.9234--50.0547 Hz.
Each naive Europe/Paris timestamp is explicitly interpreted as an instantaneous
point held over the following half-open interval. The canonical interval-average
command is:

```text
xi = clip((50.0 Hz - frequency_hz) / 0.2 Hz, -1, 1)
```

Positive `xi` means upward/discharge response. Open Energy Lab battery power is
charge-positive, so replay converts signs exactly once:

```text
requested_fcr_power_kw = -xi * committed_fcr_capacity_kw
requested_combined_power_kw = baseline_power_kw + requested_fcr_power_kw
```

The normalized fixture records the pinned revision, raw digest, source
timezone, point-to-interval declaration, formula, clipping, attribution,
content fingerprint, and full artifact fingerprint. Loading the normalized
fixture never reopens the external file.

## Single-Owner Responsibility Matrix

| Responsibility | Single owner | Boundary |
| --- | --- | --- |
| ENTSO-E retrieval and market-source normalization | `open_energy_lab.market.entsoe` | Explicit authenticated fetch/refresh only |
| Canonical market-artifact validity and integrity | `open_energy_lab.market.artifact` | Immutable A44/combined-A81 manifest and offline load |
| Canonical activation-artifact validity and integrity | `open_energy_lab.market.activation` | Source-independent import modes, exact tiling, fingerprints |
| Deterministic fixed energy/FCR schedules | `open_energy_lab.control.stacked_service` | No activation lookahead and no optimization |
| Battery-constrained physical delivery | `open_energy_lab.simulator.stacked_service` | Existing `apply_power_request`, attribution, aggregation |
| Day-ahead/FCR settlement | `open_energy_lab.simulator.fcr_settlement` | Accepted schedules and explicit penalties only |
| Robust bidding and optimization | Later robust-bidding feature | Not implemented or implied by Feature 010 |

The explicit `examples/bess_stacked_services/import_reference_activation.py`
consumer parses the pinned RTE representation and delegates canonical artifact
validity to `market.activation`; it is not a second owner of artifact semantics.

## Demonstration Configuration And Gate

Once the ENTSO-E gate passes, the recorded demonstration must use exactly:

- one 100 kWh battery with a 10--90 kWh operating range;
- 50 kW charge and discharge limits;
- 0.92 charge and discharge efficiency;
- 50 kWh initial stored energy;
- the existing 5 kW price-threshold request below 475 EUR/MWh or above
  540 EUR/MWh, clipped only for symmetric FCR power headroom;
- six fixed four-hour 5 kW symmetric-FCR commitments;
- zero non-delivery penalty; and
- a report-only 50 kWh terminal target.

Expected baseline intervals, market observation references, physical traces,
settlement totals, and fingerprints must be generated from the accepted
fixtures. They must not be inferred from the research plan. Until the gate
passes, `france_2022-08-19_market_v1.json` and
`france_2022-08-19_expected_replay_v1.json` remain absent, and the real replay
and reference benchmark report the recorded skip reason.

## Settlement And Scope

Day-ahead revenue settles the accepted hourly baseline, not realized physical
delivery. FCR capacity revenue settles the committed eligible kW converted to
MW, aligned EUR/MW/h remuneration, and block duration. FCR non-delivery is
measured relative to the accepted baseline. A penalty is zero unless an
explicit deterministic EUR/kWh rule is supplied. Activation-energy payment,
imbalance settlement, and degradation cost are reported as `not_modeled`.

Feature 010 does not migrate robust optimization, aFRR, mFRR, generic reserve
products, bid selection, stochastic lookahead, terminal recovery dispatch,
network fetch-on-missing, notebooks, SLURM, W&B, GPU, or legacy runtime behavior.

## Reference Benchmark Record

The required one-warm-up/five-measurement reference benchmark cannot be accepted
until the two blocked fixtures exist. No timing sample is recorded as passing
while correctness inputs are absent. When resumed, record CPU model, allocated
cores/processes, available memory, operating system, Python version, repository
revision, and all five end-to-end timings here without modifying the expected
fixture during validation.

An explicit attempt on 2026-08-21 produced the following preflight record:

| Field | Observed value |
| --- | --- |
| CPU model | Intel Xeon Gold 5218R at 2.10 GHz |
| Host logical CPUs | 80 |
| Process-visible allocation | 10 CPUs, one CPython process, no deliberate parallelism |
| Memory | 503 GiB total, 428 GiB available at preflight |
| Operating system | Linux 6.8.0-124-generic x86_64 GNU/Linux |
| Python | CPython 3.14.6 |
| Repository revision | `9e8adc5` plus the pending Phase 7 documentation changes |
| Command | `uv run pytest tests/integration/simulator/test_stacked_service_real_replay.py -m reference_benchmark -q` |
| Outcome | skipped before warm-up because the market and expected-replay fixtures are gated and absent |
| Five timing samples | not produced; no correctness input was available to benchmark |

This is not a passing benchmark record and T050 remains incomplete. The
expected-result fixture was absent and therefore was not modified.
