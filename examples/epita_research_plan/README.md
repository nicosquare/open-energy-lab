# EPITA Research-Plan Figures

This directory supports the publication-safe OEL figures used by the
standalone EPITA research proposal in the `thesis` submodule. The proposal uses
selected outputs from the TPM planning and authored robust-FCR notebooks. It
does not use restricted BESS stacked-services or restoration-service figures.

From the OEL repository root, generate a temporary copy with:

```bash
uv run --offline --locked --no-sync --group notebook python -m \
  examples.epita_research_plan.generate_figures
```

The compact generator remains available for regenerating the two-panel
TPM-embedding/FCR evidence figure:

```bash
uv run --offline --locked --no-sync --group notebook python -m \
  examples.epita_research_plan.generate_figures \
  --output-dir thesis/img/epita
```

It uses public OEL APIs for the robust restriction solve and reads only
committed, reviewed evidence.

The proposal itself uses a more detailed selection from the research
notebooks. First execute
`examples/tpm_planning/discrete_study_walkthrough.ipynb`. Then execute
`examples/robust_fcr_bidding/robust_fcr_bidding_walkthrough.ipynb` with
`EXPORT_FIGURES=True`. Stage the selected outputs with:

```bash
bash examples/epita_research_plan/stage_notebook_figures.sh
```

The staging script converts the two Matplotlib SVG planning figures to PDF and
copies the two PNG FCR figures into `thesis/img/epita`. The outputs illustrate
existing library capabilities; they are not results from the proposed EPITA
community-control experiment. Recorded real-data plots from the ENTSO-E and
RTE notebooks are excluded from the proposal because they have separate access
and redistribution restrictions.
