# French BESS Stacked-Services Examples

This directory is the consumer surface for Feature 010. The examples show the
explicit boundary between source acquisition and deterministic offline replay;
reusable retrieval, artifact, activation, schedule, battery, and settlement
behavior belongs under `src/open_energy_lab`, not in these scripts.

The consumers are implemented. The RTE activation fixture is validated and
committed. The obsolete A81 request assumptions have been replaced by the
current R3 combined A81 contract; the ENTSO-E market and derived replay
fixtures remain uncommitted because A44 redistribution lacks a documented
basis. The technical and legal gates are recorded separately in
`tests/fixtures/market/README.md`.

## Consumer Map

| Consumer | Network or secret | Responsibility |
| --- | --- | --- |
| `fetch_french_period.py` | Explicit ENTSO-E HTTPS operation; caller token required | Fetch or refresh canonical A44/combined-A81 market artifacts |
| `import_reference_activation.py` | No network; caller-supplied local raw file | Verify and normalize the selected RTE PT10S activation trace |
| `generate_reference_replay.py` | No network; validated local artifacts | Build and independently reconcile the gated fixed replay fixture |
| `run_offline_replay.py` | None | Load recorded artifacts, replay the fixed schedule, and compare deterministic results |

No consumer downloads on import, fetches on cache miss, chooses an alternative
source, or moves source-specific types into the simulator.

## Explicit Fetch And Refresh

`fetch_french_period.py` exposes `fetch` and `refresh` modes. It reads
`ENTSOE_API_TOKEN` only immediately before calling the explicit ENTSO-E producer
and passes the token as a separate keyword-only operation argument. The token
is never part of a request object, path, cache key, artifact, log, diagnostic,
or fingerprint.

Copy `.env.example` to the ignored `.env` file at the repository root and
replace its placeholder, or export `ENTSOE_API_TOKEN` in the calling shell. The
CLI's optional `--env-file` path reads only that key with no interpolation and
does not mutate the process environment. An already-exported value takes
precedence.

The intended fetch invocation is:

```bash
uv run python examples/bess_stacked_services/fetch_french_period.py \
  --mode fetch \
  --start 2022-08-18T22:00:00Z \
  --end 2022-08-19T22:00:00Z \
  --destination artifacts/market \
  --env-file .env
```

The caller supplies the credential through the dedicated environment variable
without putting its value in command arguments. A successful fetch prints only
a token-free immutable artifact path and sanitized source summary. It publishes
only after the A44 window and both combined A81 measures validate.

Refresh additionally receives `--current PATH`. Its result is exactly one of
`unchanged`, `published`, or `revision_regression`; it never overwrites the
current artifact. Transient source failures receive at most three total
attempts, permanent client failures receive one, and every failed operation
leaves no complete or partially referenced artifact.

Acquisition is an explicitly selected workflow. It is not invoked by package
import, artifact loading, fixture review, schedule construction, or replay.
The exact R3 requests and response mapping are documented in
[ENTSO-E Transparency Platform integration](../../docs/architecture/entsoe-transparency-platform.md).

## Explicit Activation Import

`import_reference_activation.py` accepts a caller-supplied local copy of
the selected RTE frequency file, its expected SHA-256 digest, source revision,
period, and destination. It performs no download and no notebook execution. It
validates gap-free naive Europe/Paris timestamps, applies the declared
left-hold PT10S conversion and `clip((50-f)/0.2,-1,1)` normalization, and
publishes a separately fingerprinted activation artifact. The accepted pinned
file digest is
`314a84556383161e9a9628b31eaa885e471f04db213a971c4f25efaef1053a8a`;
the reproducible command is recorded in the feature quickstart.

This regeneration workflow is optional and is not part of routine validation.

## Default Offline Replay

`run_offline_replay.py` is the default demonstration consumer:

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

At present the command exits with status 2 and identifies
`france_2022-08-19_market_v1.json` and
`france_2022-08-19_expected_replay_v1.json` as missing because the credentialed
publication gate has not passed. Technical source compatibility is already
validated. That is the required behavior, not an installation error.

`generate_reference_replay.py` is the explicit private fixture-production
step after a successful local market fetch. It records the full threshold and
headroom derivation plus independently reconciled replay totals and
fingerprints. When A44 remains local-only, it rejects every destination outside
the ignored `artifacts/` tree; producing a local expected replay is not
permission to commit either restricted file. See the feature quickstart for
the exact generation and private-benchmark commands.

## Experimental-v1 Library Surface

Source-independent market and activation artifacts resolve lazily from
`open_energy_lab.market`; deterministic baseline builders resolve lazily from
`open_energy_lab.control`; replay and settlement resolve lazily from
`open_energy_lab.simulator`. The source-bearing producer remains the focused
`open_energy_lab.market.entsoe` module and is never imported by offline replay.

The complete API names, fixture paths, fetch/refresh commands, activation
regeneration command, validation selections, and failure semantics are kept in
`specs/010-bess-stacked-services/quickstart.md`.

## Validation Selection

Routine review is fixture-backed and excludes both opt-in markers:

- `live_entsoe` selects the credentialed current-source compatibility check.
- `reference_benchmark` selects the reference-host performance protocol.

Network, token, or reference-host unavailability is reported separately and
does not weaken deterministic offline validation.
