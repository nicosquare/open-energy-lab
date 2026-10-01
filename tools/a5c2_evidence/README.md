# A5c-2 evidence: the saved rolling-study result lost only the agreed fields

Same tooling as A5b (`snapshot_plugin.py`, `compare.py`; see commit `daa4287`).
`comparison_vs_main.txt` compares `main` (after A5c-1) with this branch. The
saved `RollingFCRStudyResult` is flagged as changed, as intended. A path-level
summary of every saved result in the control, simulator and parity tests:

- removed: nested seals (`revision_`, `envelope_`, `state_link_`,
  `continuity_`, `aggregate_`, `classification_fingerprint`), links to
  unsaved objects (`problem_`, `solve_result_`, `feasibility_audit_`,
  `input_`, `finalizer_*`, `replay_`, `settlement_`, `predecessor_*`,
  `successor_problem_`, `accepted_fixings_`, `rounding_evidence_`,
  `causal_prefix_fingerprint`), `fingerprint_evidence`,
  `source_fingerprints`, `stable_runtime_evidence`, and per-record
  `manifest_fingerprint`, `profile_fingerprint`, `profile_id`;
- added: nothing;
- changed (other than hash values): only `semantics_version` (v1 -> v2).

Other flagged classes (price inputs, time contract) only gained `to_dict()`
calls on objects not serialized before in that test; every such output
already appears elsewhere in the baseline. These files are removed in the
next commit.
