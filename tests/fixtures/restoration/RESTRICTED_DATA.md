# Restricted Restoration-Service Data

The following Feature 011 files are restricted to authorized collaborators in
this private repository:

- `france_2026-08-20_afrr_market_v1.json`
- `france_2026-08-20_afrr_scenario_v1.json`
- `france_2026-08-15_mfrr_market_v1.json`
- `france_2026-08-15_mfrr_scenario_v1.json`
- `france_restoration_expected_results_v1.json`

The files are not offered under the repository's Apache-2.0 license. They must
not enter a wheel, source distribution, release, public CI artifact, public
fork or mirror, or external artifact store. Remove them or complete a new
rights and policy assessment before changing repository visibility.

## Permitted Repository State

```text
repository_storage: permitted_private_restricted
repository_publication: prohibited
package_distribution: prohibited
release_distribution: prohibited
public_ci_artifact: prohibited
public_mirror_or_fork: prohibited
external_artifact_store: prohibited
visibility_change_action: remove_or_reassess_before_change
```

The market files preserve normalized RTE Balancing Energy v5.2 observations.
The scenario and expected-result files remain restricted because they are
deterministically derived from those values. No production raw market body,
OAuth response, credential, or access token is committed.

This restriction does not apply to project-authored files under
`synthetic_rte/` or to the hand-calculable `manual_afrr_v1.json` and
`manual_mfrr_v1.json` oracles. Those inputs must be visibly labelled synthetic
and must not claim to be observed asset dispatch.

The governed acquisition, staging, attribution, fingerprint, and refresh
records are completed by the later Feature 011 fixture-production tasks and the
project-wide restricted-reference documentation.
