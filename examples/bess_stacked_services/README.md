# French BESS Stacked-Services Examples

This directory is the consumer surface for Feature 010. The examples show the
explicit boundary between source acquisition and deterministic offline replay;
reusable retrieval, artifact, activation, schedule, battery, and settlement
behavior belongs under `src/open_energy_lab`, not in these scripts.

The consumers are implemented. The RTE activation fixture is validated and
committed. The obsolete A81 request assumptions have been replaced by the
current R3 combined A81 contract. The repository owner has confirmed that this
repository is private, so the real reference fixtures may be stored for
authorized collaborators under the restricted-data policy; public and package
distribution remain prohibited. The exact market and expected replay are now
staged and validated for the default offline consumer.

## Consumer Map

| Consumer | Network or secret | Responsibility |
| --- | --- | --- |
| `fetch_french_period.py` | Explicit ENTSO-E HTTPS operation; caller token required | Fetch or refresh canonical A44/combined-A81 market artifacts |
| `import_reference_activation.py` | No network; caller-supplied local raw file | Verify and normalize the selected RTE PT10S activation trace |
| `stage_private_reference_market.py` | No network or token; explicit private-repository acknowledgement | Stage the fixed market fixture with restricted storage and prohibited-publication metadata |
| `generate_reference_replay.py` | No network; validated local or privately staged artifacts | Build and independently reconcile the restricted fixed replay fixture |
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

`stage_private_reference_market.py` is the explicit bridge between the ignored
credentialed output and this private repository. It accepts only the exact
validated reference period, requires
`--acknowledge-private-restricted-repository`, preserves normalized content,
and records that repository publication, packages, releases, public forks and
mirrors, and external uploads are prohibited.

`generate_reference_replay.py` records the full threshold and headroom
derivation plus independently reconciled replay totals and fingerprints.
Unstaged A44 data can write only beneath ignored `artifacts/`; a repository
fixture can be generated only from the privately staged market artifact. See
the feature quickstart and the
[restricted-fixture policy](../../docs/migration/restricted-reference-fixtures.md)
for the exact commands. The three real-data fixtures must be removed before
this repository or its relevant history is made public.

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
