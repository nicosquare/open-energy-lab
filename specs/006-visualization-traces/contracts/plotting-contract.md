# Contract: Optional Static Plotting Layer

This contract defines the experimental plotting boundary for the visualization
MVP.

## Purpose

The plotting layer must add basic static visual rendering for supported
single-run traces without weakening the lightweight stable inspection surface.

## Required Scope

The experimental plotting layer must support:

- basic static single-run plots for supported trace series
- plotting from inspection views already built in memory
- plotting from supported persisted outputs loaded later

## No-Resimulation Rule

Plot generation must:

- consume an existing supported run output, inspection view, or compatible
  persisted output
- never rerun the simulator
- never require access to the original simulation process after the run has
  completed

## Optional Dependency Boundary

Plotting support must:

- remain outside the always-available stable inspection/reporting imports
- keep any plotting backend optional
- fail deterministically when plotting is requested without the optional
  backend or without supported series inputs

## Deferred Directions

This MVP does not require:

- dashboards
- interactive browser views
- notebook-first rendering
- rendered side-by-side comparison plots
- visualization-owned artifact orchestration or job execution
