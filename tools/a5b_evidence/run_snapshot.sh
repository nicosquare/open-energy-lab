#!/usr/bin/env bash
# usage: run_snapshot.sh <label>   (runs relevant FCR tests incl. slow, records to_dict outputs)
set -u
cd /home/nicolas.avila/dev/open-energy-lab
export A5B_SNAPSHOT=tools/a5b_evidence/$1.jsonl PYTHONPATH=tools/a5b_evidence
uv run pytest -p snapshot_plugin -m "not notebook and not licensed_gurobi and not live_entsoe and not live_rte and not reference_benchmark and not external_reference_data" \
  tests/unit/control tests/integration/control tests/unit/simulator tests/integration/simulator tests/parity \
  -q -p no:cacheprovider --no-header --color=no -p no:randomly > tools/a5b_evidence/$1.log 2>&1
echo "exit=$?" >> tools/a5b_evidence/$1.log
