#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
destination="${1:-${repository_root}/thesis/img/epita}"
planning_root="${repository_root}/tmp/abu-dhabi-autonomy-study/visualizations"
fcr_root="${repository_root}/tmp/robust-fcr-bidding-notebook/figures"

planning_figures=(
  "split-risk-heatmaps.svg"
  "cost-risk-frontier.svg"
)
fcr_figures=(
  "joint_bid_and_headroom.png"
  "post_acceptance_stress_replay.png"
)

for figure in "${planning_figures[@]}"; do
  if [[ ! -f "${planning_root}/${figure}" ]]; then
    echo "missing TPM notebook figure: ${planning_root}/${figure}" >&2
    echo "execute examples/tpm_planning/discrete_study_walkthrough.ipynb first" >&2
    exit 1
  fi
done

for figure in "${fcr_figures[@]}"; do
  if [[ ! -f "${fcr_root}/${figure}" ]]; then
    echo "missing robust-FCR notebook figure: ${fcr_root}/${figure}" >&2
    echo "execute robust_fcr_bidding_walkthrough.ipynb with EXPORT_FIGURES=True first" >&2
    exit 1
  fi
done

if ! command -v libreoffice >/dev/null 2>&1; then
  echo "libreoffice is required to convert the notebook SVG outputs to PDF" >&2
  exit 1
fi

mkdir -p "${destination}"
conversion_directory="$(mktemp -d)"
libreoffice --headless --convert-to pdf --outdir "${conversion_directory}" \
  "${planning_root}/split-risk-heatmaps.svg" \
  "${planning_root}/cost-risk-frontier.svg"

mv "${conversion_directory}/split-risk-heatmaps.pdf" "${destination}/"
mv "${conversion_directory}/cost-risk-frontier.pdf" "${destination}/"
rmdir "${conversion_directory}"

install -m 0644 \
  "${fcr_root}/joint_bid_and_headroom.png" \
  "${destination}/joint_bid_and_headroom.png"
install -m 0644 \
  "${fcr_root}/post_acceptance_stress_replay.png" \
  "${destination}/post_acceptance_stress_replay.png"

echo "staged notebook figures in ${destination}"
