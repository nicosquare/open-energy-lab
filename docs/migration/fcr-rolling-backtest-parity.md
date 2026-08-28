# FCR rolling backtest parity evidence ledger

Feature 015 migrates the pinned reference's five non-intraday executable
profiles into an offline-by-default native rolling study. Feature 013 remains
the optimizer; Feature 012 remains the sole battery replay and settlement
owner. This ledger records which claims are supported as implementation and
validation progress.

## Source behavior map

| Reference source | Behavior used by Feature 015 |
| --- | --- |
| `baselines/robust_storage_bidding/code/01_datastruct.jl:3-48` | Source sign convention, battery and uncertainty defaults, terminal target, model kind, and default time limit. |
| `baselines/robust_storage_bidding/code/02_model.jl:15-32` | Extended hourly indices and fixed predecessor energy overlap. |
| `baselines/robust_storage_bidding/code/02_model.jl:34-75` | Exact no-regulation hourly formulation. |
| `baselines/robust_storage_bidding/code/02_model.jl:86-99,137-143` | Reserve indices, non-intraday zero adjustment, and fixed predecessor reserve overlap. |
| `baselines/robust_storage_bidding/code/02_model.jl:175-188,252-263,289-291` | Robust state propagation, full-frame objective and terminal rule, and lower-index derivation. |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:5-83` | Activation concatenation, predecessor-tail/current-day replay ordering, and cutoff replay. |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:86-158` | Ten-second replay behavior and three-decimal persisted state. These equations are evidence for Feature 012 checks, not code to duplicate in Feature 015. |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:161-204` | Predecessor-result finalization and the limitation of the hard-coded restriction `bilinear_violations` field. |
| `baselines/robust_storage_bidding/code/04_parse_results.jl:4-39,43-100` | Source field meanings, silent missing-file behavior to reject, and workbook aggregation formulas. |
| `baselines/robust_storage_bidding/code/05_dates.txt:1-1453` | Ordered source date list and DST exclusions. |
| `baselines/robust_storage_bidding/code/11.jl:23-95` | Relaxation with independent reset days, result directory 01. |
| `baselines/robust_storage_bidding/code/12.jl:23-95` | Restriction with independent reset days, result directory 02. |
| `baselines/robust_storage_bidding/code/13.jl:23-103` | Sequential no-regulation midnight profile, result directory 03. |
| `baselines/robust_storage_bidding/code/14.jl:23-104` | Sequential 08:00 restriction and accepted-overlap carry, result directory 04. |
| `baselines/robust_storage_bidding/code/15.jl:23-104` | Sequential midnight restriction and stored-energy carry, result directory 05. |

The executable profile crosswalk is deliberately separate from paper labels:
scripts 11/12/13/14/15 correspond to paper Experiments 1/2/4/5/3 and workbook
columns 11/12/14/15/13. Script 13's executable time limit and the workbook's
energy metric also require explicit discrepancy evidence.

## Evidence limits

- No Table A1 parity claim is made. The bounded four-day rerun cannot prove a
  full-history aggregate, and the workbook/paper metric mapping is not fully
  interchangeable with executable output.
- No optimality claim is made from source JSON alone. Several retained logs
  describe time-limited feasible incumbents with upper bounds.
- Displayed three-decimal source values define closed precision intervals;
  they are not exact hidden solver decisions or feasibility proof.
- The restriction JSON's `bilinear_violations=0` field is not an independent
  audit. Native compatibility requires Feature 013's formulation audit.
- Exact 08:00 restart parity may be unavailable because the source did not
  persist the full-precision predecessor decisions it fixed in memory.
- The last bounded 08:00 delivery date remains unfinalized without a following
  successor solve. The first date is initialization evidence.
- Activation-backed replay is unavailable unless a caller explicitly supplies
  the governed Feature 012 CSV. No implementation searches for it.

## Validation record

No implementation checkpoint has been claimed yet. Each phase will append its
exact commands, pass counts, semantic fingerprints, and actionable optional
skips here after the corresponding task group passes.
