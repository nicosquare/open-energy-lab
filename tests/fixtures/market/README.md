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

## Offline Review Contract

Routine unit and integration tests use only committed synthetic or canonical
fixtures and injected transports. Loading fixtures, constructing schedules,
replaying the battery, and settling results must make zero network calls and
must not read `ENTSOE_API_TOKEN`. Live compatibility and reference-host
benchmark checks are explicitly selected through their dedicated pytest
markers and do not weaken the offline gates when unavailable.
