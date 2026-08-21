# French BESS Stacked-Services Examples

This directory is the consumer surface for Feature 010. The examples show the
explicit boundary between source acquisition and deterministic offline replay;
reusable retrieval, artifact, activation, schedule, battery, and settlement
behavior belongs under `src/open_energy_lab`, not in these scripts.

Phase 1 establishes this outline. Later tasks add the consumers and validated
fixtures named below.

## Consumer Map

| Consumer | Network or secret | Responsibility |
| --- | --- | --- |
| `fetch_french_period.py` | Explicit ENTSO-E HTTPS operation; caller token required | Fetch or refresh canonical A44/A81/A89 market artifacts |
| `import_reference_activation.py` | No network; caller-supplied local raw file | Verify and normalize the selected RTE PT10S activation trace |
| `run_offline_replay.py` | None | Load recorded artifacts, replay the fixed schedule, and compare deterministic results |

No consumer downloads on import, fetches on cache miss, chooses an alternative
source, or moves source-specific types into the simulator.

## Explicit Fetch And Refresh

`fetch_french_period.py` will expose `fetch` and `refresh` modes. It reads
`ENTSOE_API_TOKEN` only immediately before calling the explicit ENTSO-E producer
and passes the token as a separate keyword-only operation argument. The token
is never part of a request object, path, cache key, artifact, log, diagnostic,
or fingerprint.

The intended fetch invocation is:

```bash
uv run python examples/bess_stacked_services/fetch_french_period.py \
  --mode fetch \
  --start 2022-08-18T22:00:00Z \
  --end 2022-08-19T22:00:00Z \
  --destination artifacts/market
```

The caller supplies the credential through the dedicated environment variable
without putting its value in command arguments. A successful fetch prints only
a token-free immutable artifact path and sanitized source summary. It publishes
only after all required France A44, A81, and A89 windows validate.

Refresh additionally receives `--current PATH`. Its result is exactly one of
`unchanged`, `published`, or `revision_regression`; it never overwrites the
current artifact. Transient source failures receive at most three total
attempts, permanent client failures receive one, and every failed operation
leaves no complete or partially referenced artifact.

Acquisition is an explicitly selected workflow. It is not invoked by package
import, artifact loading, fixture review, schedule construction, or replay.

## Explicit Activation Import

`import_reference_activation.py` will accept a caller-supplied local copy of
the selected RTE frequency file, its expected SHA-256 digest, source revision,
period, and destination. It performs no download and no notebook execution. It
validates gap-free naive Europe/Paris timestamps, applies the declared
left-hold PT10S conversion and `clip((50-f)/0.2,-1,1)` normalization, and
publishes a separately fingerprinted activation artifact.

This regeneration workflow is optional and is not part of routine validation.

## Default Offline Replay

`run_offline_replay.py` will be the default demonstration consumer:

```bash
uv run python examples/bess_stacked_services/run_offline_replay.py
```

It loads and verifies the committed canonical market, activation, and expected
replay fixtures; loads the recorded fixed hourly energy and four-hour FCR
schedules; replays the existing charge-positive battery transition at PT10S;
settles the accepted schedule; and compares trace, result, and component
fingerprints. The same inputs must produce identical output with network access
blocked and with no credential present.

The offline consumer has no transport argument and never reads
`ENTSOE_API_TOKEN`. Missing, incomplete, incompatible, or corrupt inputs fail
before normal replay; the consumer does not fill, trim, interpolate, prorate,
or fetch a replacement.

## Validation Selection

Routine review is fixture-backed and excludes both opt-in markers:

- `live_entsoe` selects the credentialed current-source compatibility check.
- `reference_benchmark` selects the reference-host performance protocol.

Network, token, or reference-host unavailability is reported separately and
does not weaken deterministic offline validation.
