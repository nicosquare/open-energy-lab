# A5b evidence: in-memory fingerprint removal changed no content

`snapshot_plugin.py` records every `to_dict()` output of the FCR control and
simulator dataclasses, per test. `run_snapshot.sh LABEL` runs the control,
simulator and parity tests (slow included) with it; `compare.py BASE NEW`
checks, per (test, class):

- every new output already existed in the baseline once the removed
  fingerprint keys are dropped and fingerprint values are masked
  (fewer outputs is fine: hashing used to call `to_dict()`);
- `RollingFCRStudyResult`, the only saved object, lost no keys and has the
  same content apart from fingerprint values;
- runtime fields (`runtime_seconds`, `elapsed_seconds`) are ignored; two
  baseline runs on `main` compare clean with only those masked.

`final_comparison.txt` is the comparison of `main` against the last A5b
commit: only the intended fingerprint keys are dropped, and nothing else
differs. The 186 MB snapshots are not committed. These files are removed in
the next commit.
