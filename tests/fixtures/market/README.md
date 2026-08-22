# Market Fixtures

This directory is the offline evidence boundary for Feature 010, French BESS
stacked services. Fixtures are versioned, deterministic, and small enough for
routine review. Source retrieval and raw-source handling remain explicit
producer workflows; simulator tests consume only validated canonical artifacts.

## Planned Layout

```text
market/
├── README.md
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
- The three `france_2022-08-19_*` files form the gated real demonstration:
  canonical market input, separately provenanced activation input, and expected
  replay output. They must be mutually linked by their recorded fingerprints.

Later phases create these files. Their names here reserve the reviewed fixture
layout; their presence must never be inferred as proof that a source gate passed.

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

## Gated Real-Fixture Policy

The selected market period is the Europe/Paris delivery day 2022-08-19, or UTC
`[2022-08-18T22:00:00Z, 2022-08-19T22:00:00Z)`. The normalized market fixture
may be committed only after one explicitly selected credentialed workflow
proves all of the following for that exact period:

- complete compatible France A44 day-ahead price coverage;
- complete compatible A81 symmetric-FCR contracted-volume coverage;
- complete A89 capacity-price coverage aligned to the same FCR product;
- accepted document identities, revisions, units, resolutions, and response
  digests; and
- a documented attribution and legal basis for redistributing the normalized
  fixture and for any separately retained raw sidecar.

If any completeness, compatibility, integrity, or reuse gate fails, do not
publish the real market fixture. Record the blocker in this README during the
fixture-production task. Do not fill gaps, interpolate, substitute RTE prices,
patch with synthetic observations, or choose another period without a
specification change.

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

The ENTSO-E market-fixture gate remains **blocked** after an explicitly
credentialed production execution. The token was read from the ignored `.env`
file, passed separately to the transport, and absent from captured output,
exceptions, paths, and written bytes. Network and authentication succeeded.
The A44 response for UTC
`[2022-08-18T22:00:00Z, 2022-08-19T22:00:00Z)` validated after preserving two
current wire-profile details: Article 12.1(d) omits the response process field,
and its exact hourly duration is spelled `PT60M` rather than canonical `PT1H`.

Acquisition then stopped at A81. The production API returned permanent HTTP
400 on the first attempt, as required for a non-retryable client response. A
sanitized finite parameter audit proved that the API recognizes and requires
`BusinessType` and `Type_MarketAgreement.Type`, but rejected every official
agreement code for the France control area, FCR business type A95, and selected
period with acknowledgement code 999, “The provided parameters do not match
the dataItem parameters or values.” A89 was not requested after the required
A81 series failed. Four producer destinations were inspected and contained no
manifest or sidecar.

The legal-reuse gate independently fails. The ENTSO-E list checked on
2026-08-22 places contracted reserve amount and reserved-capacity price (the
A81/A89 concepts, items 22 and 23) in its CC BY 4.0 free-reuse subset, but does
not list Article 12.1(d) day-ahead prices (A44). The current Terms of Use require
users to check that list and seek the Primary Owner's agreement where reuse may
prejudice its rights. No A44 Primary Owner permission was supplied, so this
repository has no documented basis for redistributing a normalized A44
fixture. Sources:

- `https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions`
- `https://transparencyplatform.zendesk.com/hc/article_attachments/40921869379729`
- `https://transparencyplatform.zendesk.com/hc/en-us/articles/41986091964305-Archives-for-legacy-Transparency-Platform-publications`

Consequently:

- `france_2022-08-19_market_v1.json` is intentionally absent;
- `france_2022-08-19_expected_replay_v1.json` cannot be produced; and
- no partial market data, RTE price substitute, synthetic replacement, gap
  fill, interpolation, or alternate delivery period has been used.

Resume the gate only after the specification identifies a currently compatible
source contract for all three required series and documents permission to
redistribute A44. A token alone no longer resolves either blocker.

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
