# Market Fixtures

This directory is the offline evidence boundary for Feature 010, French BESS
stacked services. Fixtures are versioned, deterministic, and small enough for
routine review. Source retrieval and raw-source handling remain explicit
producer workflows; simulator tests consume only validated canonical artifacts.

## Layout

```text
market/
├── README.md
├── RESTRICTED_DATA.md
├── synthetic_entsoe/
│   └── ...                         # redistributable XML parser cases
├── manual_stacked_service_v1.json
├── france_2022-08-19_market_v1.json
├── france_2022-08-19_activation_v1.json
└── france_2022-08-19_expected_replay_v1.json
```

- `synthetic_entsoe/` contains minimal authored responses for success, source
  failure, revision, coverage, unit, product, XML-safety, and DST tests. These
  are test documents, not recorded production responses.
- `manual_stacked_service_v1.json` is the published four-hour arithmetic
  oracle defined by the feature contracts.
- The three `france_2022-08-19_*` files form the restricted real demonstration:
  canonical market input, separately provenanced activation input, and expected
  replay output. They must be mutually linked by their recorded fingerprints,
  excluded from packages/releases, and kept inside the private repository.

## Credential And Token Prohibition

An ENTSO-E API token is transient operation input. No token may appear in this
directory or in any fixture value, filename, path, source locator, query-window
identity, digest input, cache identity, test recording, exception, captured
output, or documentation example. Tests use a conspicuous sentinel token and
scan produced paths, bytes, object representations, logs, stdout, and stderr for
zero occurrences.

Do not commit `.env` files, copied request URLs, authorization headers, shell
transcripts, HTTP cassettes, or source responses containing credential-bearing
request material. A fixture must remain usable with no token in the environment.

## Raw-Response And Sidecar Rule

Canonical market artifacts never embed raw ENTSO-E response bytes. Every source
response is represented by token-free semantic request metadata, byte count,
media type, retrieval provenance, SHA-256 digest, and an explicit retention and
redistribution status.

The default is `digest_only`. A real raw response may be retained only when the
recorded source terms explicitly permit it. Such a response is a separately
managed sidecar and must:

- use a relative locator contained beneath the declared artifact root;
- reject absolute paths, traversal, and symlink escape;
- have its bytes verified against the manifest SHA-256 digest on every load;
- be staged before the manifest, with the manifest published atomically last;
- carry the attribution, terms version/date, and transformation record that
  justify retention and redistribution.

A missing or mismatched sidecar invalidates an artifact that claims
`sidecar_retained`. When permission is absent or uncertain, retain only the
digest and source metadata. Redistributable synthetic XML cases are authored
test inputs and must be labeled as such rather than presented as raw evidence.

## Restricted Real-Fixture Policy

The selected market period is the Europe/Paris delivery day 2022-08-19, or UTC
`[2022-08-18T22:00:00Z, 2022-08-19T22:00:00Z)`. The normalized market fixture
may be staged only after one explicitly selected credentialed workflow proves
all of the following for that exact period:

- complete compatible France A44 day-ahead price coverage;
- complete compatible combined A81 symmetric-FCR contracted-volume and
  procurement-price coverage from the same points and document;
- accepted document identities, revisions, units, resolutions, and response
  digests; and
- documented attribution, raw-response retention, and storage policy.

If any completeness, compatibility, integrity, or storage gate fails, do not
stage the real market fixture. Do not fill gaps, interpolate, substitute RTE
prices, patch with synthetic observations, or choose another period without a
specification change.

The repository owner confirmed on 2026-08-22 that this repository is private
and limited to authorized collaborators. That permits restricted repository
storage; it does not grant public redistribution. All three real-data fixtures
are governed by `RESTRICTED_DATA.md` and
`docs/migration/restricted-reference-fixtures.md`. They must never be included
in packages, releases, public CI artifacts, public forks or mirrors, or
external artifact stores, and must be removed before repository visibility is
changed to public.

The activation fixture has an independent gate. Its explicit regeneration
consumer accepts a caller-supplied local RTE frequency file, verifies the
recorded raw digest and source revision, rejects gaps and duplicates, and
publishes only the normalized PT10S trace permitted for reuse. The external raw
file and its notebook are not routine test dependencies.

## 2026-08-21 Gate Execution Record

The independent RTE activation gate passed using the exact file at
`lauinger/robust-storage-bidding@7e44738bb30e5c8204efe40103b9be4c2203685c:data_processing/freq_data/RTE_Frequence_2022_08.txt`.
The complete caller-supplied file has SHA-256
`314a84556383161e9a9628b31eaa885e471f04db213a971c4f25efaef1053a8a`.
Direct import, without the reference notebook's gap filling or duplicate
removal, proved exactly 8,640 timestamps from local `00:00:00` through
`23:59:50`, a strict 10-second grid, and a 49.9234--50.0547 Hz range. The
committed normalized fixture is
`france_2022-08-19_activation_v1.json`; its content fingerprint is
`9f80abf7e5913b05a281f6e8c1129b7ad7c6dcab69419e6872383f3a199d26f2`
and its artifact fingerprint is
`a3463ee73afc7149f1a75d1fa19866ddb53997fac1e054feed96203d0943df18`.
The raw file is not committed. Attribution is to RTE Réseau de Transport
d'Électricité; the RTE Services Portal General Terms of Service Article 9,
checked on 2026-08-21, permits reuse of public data when the source is named.
The pinned reference repository records an MIT license for its software and
documentation.

## 2026-08-22 Credentialed Market-Gate Record

The original pre-R3 A81 execution is retained as a superseded diagnostic. It
authenticated and parsed A44, then received HTTP 400 because it used obsolete
`A34/A95` assumptions and expected a separate A89 document. Review of the
official Postman collection established the current 17.1.B&C profile:
`A81/B95/A52/A01`, returned as a ZIP containing a
`Balancing_MarketDocument` with both `quantity` and
`procurement_Price.amount`.

A token-safe probe and the corrected opt-in live gate for UTC
`[2022-08-18T22:00:00Z, 2022-08-19T22:00:00Z)` returned one R3 XML member with
six sparse PT30M changes covering the day. Each volume/price pair reconciles
exactly to one PT4H block. The gate passed on 2026-08-22 with 24 A44 intervals
and six aligned PT4H FCR blocks from the same A81 document. The token scan
passed. Technical compatibility is recorded separately from public
redistribution rights. No token or raw response is committed.

The public-redistribution review remains restrictive. The ENTSO-E list checked on
2026-08-22 places contracted reserve amount and reserved-capacity price (the
two combined A81 measures, items 22 and 23) in its CC BY 4.0 free-reuse subset, but does
not list Article 12.1(d) day-ahead prices (A44). The current Terms of Use require
users to check that list and seek the Primary Owner's agreement where reuse may
prejudice its rights. ENTSO-E names power exchanges or TSOs as Primary Owners
for Article 12.1(d), and RTE's French market-data page identifies the French
spot prices as EPEX SPOT property with copying or distribution subject to prior
consent. No EPEX permission was supplied, so the private-repository decision
must not be interpreted as permission to publish a normalized A44 fixture.
Sources:

- `https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions`
- `https://transparencyplatform.zendesk.com/hc/article_attachments/40921869379729`
- `https://transparencyplatform.zendesk.com/hc/en-us/articles/16647234190100-Energy-Prices-12-1-D`
- `https://www.rte-france.com/en/data-publications/eco2mix/market-data`
- `https://transparencyplatform.zendesk.com/hc/en-us/articles/41986091964305-Archives-for-legacy-Transparency-Platform-publications`

Consequently, the validated artifacts may be committed only with
`repository_storage=permitted_private_restricted` and
`repository_publication=prohibited`. The token-free
`stage_private_reference_market.py` consumer requires an explicit private-
repository acknowledgement, keeps raw evidence digest-only, preserves the
normalized content fingerprint, and creates a new policy-bearing artifact
fingerprint. No partial data, RTE price substitute, synthetic replacement, gap
fill, interpolation, or alternate delivery period is used.

## Single-Owner Boundary

| Responsibility | Owner |
| --- | --- |
| ENTSO-E retrieval and market normalization | `open_energy_lab.market.entsoe` |
| Market-artifact validity | `open_energy_lab.market.artifact` |
| Activation-artifact validity | `open_energy_lab.market.activation` |
| Fixed schedules | `open_energy_lab.control.stacked_service` |
| Physical delivery | `open_energy_lab.simulator.stacked_service` |
| Settlement | `open_energy_lab.simulator.fcr_settlement` |
| Robust bidding | A later feature, not Feature 010 |

## Offline Review Contract

Routine unit and integration tests use only committed synthetic or canonical
fixtures and injected transports. Loading fixtures, constructing schedules,
replaying the battery, and settling results must make zero network calls and
must not read `ENTSOE_API_TOKEN`. Live compatibility and reference-host
benchmark checks are explicitly selected through their dedicated pytest
markers and do not weaken the offline gates when unavailable.
