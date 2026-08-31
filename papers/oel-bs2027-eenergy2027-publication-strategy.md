# Open Energy Lab Publication Strategy: ACM e-Energy 2027 and BS2027

**Discussion date:** 2026-08-31

**Target venues:** ACM e-Energy 2027 and Building Simulation 2027 (BS2027)

**Status:** Two-paper working strategy; not yet committed study protocols

## Context and publication boundary

Open Energy Lab (OEL) is being developed as a reusable research library for energy-system
simulation, scenario generation, control, optimization, and analysis. The publication opportunity
has two complementary parts:

1. an ACM e-Energy Full Paper about OEL as a real-data, multi-market research and evaluation
   environment; and
2. a BS2027 research paper about operational control for climate-resilient district cooling, with
   OEL serving as its enabling research infrastructure.

Both contributions must remain distinct from *Tractable Probabilistic Models for Investment
Planning*, which is currently under review, and from each other.

Both new papers must exclude the following as central research contributions:

- tractable probabilistic models or SPNs for investment planning;
- probabilistic sizing of PV or battery capacity;
- chance-constrained investment or capacity planning;
- conditional MIO compilation and embedding; and
- experiments or claims that would substantially reproduce the paper currently under review.

The papers can use the non-TPM parts of OEL: real market-data artifacts, ancillary-service and
energy schedules, physical battery replay and settlement, causal control workflows, weather and
demand scenario production, building and cooling-service simulation, controller interfaces, trace
inspection, reproducibility, and artifact provenance.

BS2027 requests a 400-word abstract describing the objective, method, and expected findings. The
abstract deadline is 1 September 2026, while the full paper is due 15 January 2027. This permits a
credible forward-looking abstract as long as its promised contribution and January implementation
scope are realistic.

ACM e-Energy 2027 has a Fall and a Winter submission cycle. The configured Fall deadlines are
11 September 2026 for registration and 18 September 2026 for the paper, both Anywhere on Earth.
The Winter cycle is in January 2027, but its exact dates were not yet configured when this note was
updated. e-Energy accepts ten-page Full Papers and four-page archival Notes. The preferred target is
a Full Paper rather than rushing a Note: the central OEL contribution should be supported by a
complete multi-market comparison and should not be consumed by a preliminary archival publication.

## Recommended two-paper portfolio

The preferred strategy is not to make two versions of one paper. Each venue should own a different
research question and principal contribution.

| Dimension | ACM e-Energy 2027 Full Paper | BS2027 Research Paper |
| --- | --- | --- |
| Central question | How do market-participation strategies compare when evaluated with the same real data, information boundaries, battery physics, activation replay, and settlement rules? | Under which disturbance, forecast, and resource conditions does anticipatory control improve district-cooling resilience? |
| Principal contribution | OEL's causal, producer-neutral, multi-market experiment and evaluation environment | Scientific findings about district-cooling resilience and operational control |
| Demonstration | Real energy, FCR, aFRR, and mFRR data with heuristic, single-market, sequential, and jointly optimized strategies | New district/local cooling composition, thermal storage, service disturbances, and anticipatory control |
| Evaluation | Physical delivery, settlement, information causality, strategy comparison, reproducibility, and cross-market trade-offs | Unserved cooling, autonomy, recovery, cost, and sensitivity to forecast and disturbance conditions |
| Deliberate exclusions | TPM, investment planning, claims that the benchmark robust bidder is novel, and substantive district-cooling results | OEL architecture as the paper's main novelty, TPM, investment planning, and market bidding |

This separation changes the earlier BS-only synthesis. If both papers are pursued:

1. OEL is the principal methodological and software contribution of the e-Energy Full Paper.
2. District-cooling resilience is the principal scientific contribution of the BS2027 paper.
3. The BS paper uses and cites OEL as infrastructure without repeating the e-Energy platform claims
   or evaluation.

The e-Energy paper should not be a generic library announcement or claim that its benchmark bidding
methods are new. Its thesis is:

> Multi-market battery strategies need a common, causal, and physically consistent environment in
> which decisions from heterogeneous methods can be evaluated against the same real market data,
> realized activations, battery replay, settlement semantics, and evidence contracts. OEL makes the
> strategy replaceable while keeping the experiment and evaluation comparable.

The existing robust FCR method is one strategy producer and benchmark, not an algorithmic novelty
claim. The full demonstration should compare it with other single-market, sequential, heuristic,
or jointly optimized strategies through the same evaluation environment. The separate
district-cooling exercise must answer a domain question rather than serve as a post-hoc target used
to justify the architecture.

## Candidate titles and venue categories

### ACM e-Energy 2027

Preferred title:

> **From Decisions to Evidence: Open Energy Lab for Reproducible Multi-Market Battery Experiments**

Alternative title:

> **Separating Bids, Delivery, and Settlement: A Producer-Neutral Evaluation Environment for
> Battery Ancillary Services**

Library-forward alternative:

> **Open Energy Lab: Causal and Reproducible Evaluation of Multi-Market Energy Strategies**

Recommended submission:

- **Paper type:** Full Paper, up to ten pages excluding references and appendices
- **Methodological track:** Systems and Applied Modeling

Control and Energy Systems would only be preferable if the paper's primary novelty moved from the
experimental platform to a new control method.

### BS2027

Preferred working title:

> **Anticipatory Control for Climate-Resilient District Cooling under Compound Service
> Disruptions**

Alternative title:

> **When Does Anticipatory Control Improve District-Cooling Resilience? A Reproducible Scenario
> Study**

Recommended submission:

- **Paper type:** Research Paper
- **Theme:** Climate Resilience & Adaptation

Urban & District Scale or Building Systems, Controls & Smart Buildings are possible alternative
themes. Simulation Methods & Emerging Tools is no longer preferred when the OEL platform paper is
separated for e-Energy.

## Motivation and relationship to existing platforms

Ancillary-service research is a demanding test of an experimental platform because it combines
different decision times, product resolutions, information cutoffs, realized activations, physical
asset constraints, and settlement rules. When a study implements all of these inside one
strategy-specific script, algorithm production and evaluation can become inseparable.

OEL's proposed distinction is a complete experiment and evidence pipeline in which the market
strategy remains replaceable:

```text
versioned real-data artifacts
        |
        v
strategy-visible information at the declared cutoff
        |
        v
heuristic, optimizer, or learning-based strategy
        |
        v
accepted multi-product commitments
        |
        v
realized activation and common physical battery replay
        |
        v
product-specific settlement, metrics, provenance, and evidence
```

The paper should not assert that OEL is the first such library without evidence. A structured review
of market simulators, optimization packages, learning environments, and ancillary-service studies
should determine whether existing tools jointly provide:

- reusable real-data acquisition and immutable offline artifacts;
- explicit product, unit, timezone, resolution, and information-cutoff semantics;
- a producer-neutral commitment interface for heterogeneous strategies;
- one common physical replay for realized multi-service delivery;
- product-specific settlement and failure accounting;
- reproducible multi-day state carry-over and causal rolling evaluation; and
- versioned provenance linking source data, decisions, replay, and reported results.

The defensible claim is not merely that other code is unavailable. It is that OEL is designed to
compare different market-participation strategies without allowing each strategy to redefine its
data, physics, or evaluation environment. CityLearn, BOPTEST, and Sinergym remain relevant adjacent
platforms for OEL's broader energy-system ambitions, but the e-Energy related-work comparison should
prioritize market and ancillary-service research tools.

## Real-data and derived-scenario position

The e-Energy study should be grounded in real energy, FCR, aFRR, and mFRR source data acquired from
documented market APIs or pinned external datasets. Credentials may be required for acquisition,
but loading, strategy execution, replay, and analysis should remain offline once immutable artifacts
have been created.

Public RTE aFRR and mFRR observations describe the French control area, not commands delivered to an
individual battery. Any allocation of an area-level observation to the study asset must therefore
remain an explicit, fingerprinted `derived_simulation` assumption. Similarly, public prices are
market context unless the study declares a product-compatible settlement mapping; they must not be
silently presented as an observed asset invoice.

Synthetic traces can supplement real data for controlled stress tests, missing combinations, and
sensitivity analysis. They should not replace the real-data evaluation or be used to claim observed
market performance.

## ACM e-Energy Full Paper design

### Neutral research question

The paper should ask:

> How do heuristic, single-market, sequential, and jointly optimized battery strategies compare
> when they are evaluated using the same real data, information boundaries, physical constraints,
> activation replay, and settlement rules?

Supporting questions are:

1. **Evaluation consistency:** Do planning-objective comparisons agree with realized physical and
   settlement comparisons under a common evaluator?
2. **Multi-market value:** Under which data and operating conditions does joint multi-market
   coordination outperform isolated or sequential participation?
3. **Causality and state:** How do information cutoffs, activation uncertainty, and multi-day battery
   state carry-over affect comparative conclusions?
4. **Reproducibility:** Can every result be reconstructed from versioned source artifacts,
   commitments, replay configuration, and evidence identities?

OEL is the instrument for answering these questions, not the assumed conclusion. Joint optimization
may or may not outperform simpler strategies after realized replay and settlement.

### Strategy comparison

A candidate comparison should include:

- a no-ancillary-service energy baseline;
- one transparent heuristic allocation strategy;
- isolated single-market strategies;
- a sequential market-allocation strategy;
- the existing robust FCR method as a benchmark producer; and
- at least one jointly optimized multi-market strategy.

Every strategy must receive a declared information view, emit the same type of accepted commitment
bundle, and be evaluated by the same battery replay and product-specific settlement owners. The
controller set, tuning or solve budgets, acceptance assumptions, and failure policy must be fixed
before inspecting comparative results.

### Implemented foundation and required extension

The current OEL foundation already includes:

- source-independent energy and FCR schedules;
- a bidder-neutral FCR physical replay and settlement boundary;
- an existing robust FCR strategy that hands plans to that evaluator;
- causal rolling FCR evaluation with state carry-over and retained failures;
- real RTE aFRR and mFRR acquisition, immutable artifacts, and derived-scenario contracts; and
- fingerprints and evidence that separate source precision, decisions, replay, and results.

A complete multi-market paper still requires:

- one accepted multi-product commitment contract shared by all strategies;
- explicit composition of simultaneous or competing service requests;
- product-compatible activation and settlement definitions for the selected study scope;
- heuristic, sequential, isolated, and joint strategy adapters;
- conflict, priority, non-delivery, and infeasibility semantics across products; and
- a multi-day real-data study bundle large enough to support comparative conclusions.

The paper must distinguish these required extensions from capabilities already implemented. It
should not present the current area-level aFRR/mFRR demonstrations as observed asset dispatch or
claim that the robust FCR formulation itself is new.

### Minimum evidence for a credible Full Paper

- a multi-day or full-history real-data evaluation rather than one favorable reference day;
- multiple materially different strategies evaluated through one immutable environment;
- planning-objective, physical-delivery, and realized-settlement comparisons;
- isolated, sequential, and joint participation ablations;
- uncertainty intervals or ranking stability across periods and activation conditions;
- causal and non-causal or reset-versus-carry sensitivity where scientifically appropriate;
- exact replay from versioned data, commitments, configuration, and code; and
- a public, redistribution-safe artifact or documented acquisition-and-reproduction workflow.

## BS2027 district-cooling resilience study

### First submission abstract

**Proposed title:** Anticipatory control for climate-resilient district cooling under compound
service disruptions

**Plain-text abstract:**

Extreme heat increases cooling demand while also stressing electricity and district energy
infrastructure. District cooling can reduce building-level equipment requirements, but dependence
on networked cooling creates a service-resilience problem when district supply is constrained or
interrupted. Local electric cooling, thermal energy storage, photovoltaic generation, and batteries
can provide operational flexibility, although their value depends on disturbance timing, available
forecasts, initial stored energy, and the condition of the electricity grid. Previous studies have
developed optimal-control methods and virtual testbeds for district cooling, but there remains a need
for reproducible comparisons that distinguish grid failures from district-cooling failures and test
control strategies across compound disturbances and uncertain restoration.

This study investigates the conditions under which anticipatory control improves cooling-service
resilience in a hybrid district/building cooling system. The system uses district cooling during
normal operation and combines constrained local electric cooling with thermal storage, photovoltaic
generation, and battery storage as flexible resources. Physical capacities are fixed so that the
study addresses operational control rather than investment planning.

Using Open Energy Lab, we will construct reproducible weather-conditioned cooling-demand scenarios
for ordinary hot periods and extreme heat. These will be combined with separate grid and
district-cooling availability models representing individual, coincident, and sequential service
interruptions. A conventional priority controller, a perfect-forecast optimization used as an upper
reference, and a forecast-limited receding-horizon controller will be evaluated through the same
physical replay and metric definitions. Sensitivity analysis will vary forecast error, interruption
timing and duration, restoration uncertainty, disturbance severity, and initial electrical and
thermal storage states.

The primary outcomes will be unserved cooling, electrical energy not served, storage depletion time,
electrical autonomy, recovery time, peak demand, energy use, and operating cost. Expected findings
will identify regimes in which anticipatory control materially improves resilience, regimes in which
simple control is sufficient, and conditions under which forecast errors or depleted storage remove
the benefit. The resulting scenario and evaluation protocol will support transparent comparison of
building and district energy control strategies while keeping conclusions conditional on declared
model and data assumptions.

### Recommended form classification

- **Submission type:** Climate Resilience & Adaptation (CRA) - Research Paper (Abstract)
- **Presentation mode:** Oral presentation
- **Specialization / Focus:**
  - Overheating risk and thermal resilience
  - Natural hazards and extreme weather events
  - Model predictive control and advanced control strategies
  - Energy storage in buildings
  - District energy systems and networks
- **Keywords:** district cooling, climate resilience, model predictive control, compound
  disruptions, energy storage
- **Student contribution:** Select only if the contribution is mainly written by a student or
  doctoral candidate.

The currently selected **Simulation Methods & Emerging Tools (SMET)** submission type is defensible
only if OEL's simulation methodology is restored as the paper's principal contribution. Under the
two-paper strategy, CRA is the cleaner classification because the BS paper's main question and
findings concern climate resilience. Relevant secondary topic associations are Urban & District
Scale, Building Systems, Controls & Smart Buildings, and SMET.

The **Select Priority Topics** and second **Specialization / Focus** fields appear under Reviewer
Information and should describe the submitting author's reviewing expertise, not be copied
automatically from the contribution classification. Suitable selections should be limited to areas
in which the author is comfortable reviewing other papers.

The optional references field can include the most relevant district-cooling control and resilience
work after the bibliographic details have been verified. It is preferable to omit it temporarily
rather than enter incomplete citations.

### Neutral scientific question

The study should ask:

> Under which disturbance, forecast, and resource conditions does anticipatory control improve
> cooling-service resilience in a hybrid district/building cooling system?

This question does not presuppose that optimal control must help. Regimes in which it provides no
benefit, increases ordinary-day cost, or fails because forecasts are inaccurate are valid results.

### Candidate physical system

The reference system could contain:

- district cooling as the normal cooling source;
- constrained local electric cooling as backup;
- chilled-water or ice thermal-energy storage;
- a building or aggregate district cooling load;
- PV generation and battery storage;
- grid availability and district-cooling availability as separate services; and
- fixed physical capacities so that the study remains operational control, not investment planning.

If pre-cooling is treated as a control action, OEL will need a defensible zone thermal model and
indoor-comfort state. Without that model, the paper must limit its thermal claim to delivered and
unserved cooling service in RT-hours.

### Controllers

The reference comparison should include:

- a conventional priority or rule-based controller;
- a perfect-forecast optimization as an upper reference rather than a deployable policy;
- a forecast-limited receding-horizon MPC controller; and
- optionally, one reinforcement-learning controller using the same observation, action, replay,
  and metric contracts.

The controller set, information available to each controller, tuning budget, and failure behavior
must be fixed before evaluating results.

### Scenario protocol

Scenarios must be constructed independently of controller outcomes. A reasonable initial suite is:

1. ordinary hot-weather operation;
2. an extreme-heat period with both services available;
3. a grid outage while district cooling remains available;
4. a district-cooling interruption while the grid remains available;
5. coincident grid and district-cooling interruptions; and
6. sequential failures and uncertain restoration durations.

Sensitivity analysis should cover forecast error, event timing, event duration, initial storage
state, and disturbance severity. Scenario identities and random seeds should be persisted before
running controllers.

### Primary metrics

- unserved cooling in RT-hours;
- electrical energy not served;
- thermal-storage state and depletion time;
- battery state of charge and electrical autonomy;
- time to recovery after service restoration;
- ordinary-day and disturbed-day energy use;
- peak electrical demand;
- operating cost; and
- indoor discomfort only if a validated zone thermal model is included.

The main results should report distributions and sensitivity ranges, not only one favorable
trajectory.

## Required OEL extensions

The current weather-demand feature deliberately supports exactly one cooling path per scenario and
uses a deterministic kW-per-RT conversion for local electric cooling. The reference exercise will
require deliberate reusable extensions rather than paper-specific scripts:

- hybrid district and local cooling-service composition;
- a thermal-storage component and state transition;
- explicit district-cooling availability and capacity;
- separate grid and district-service disturbance models;
- forecast information and forecast-error contracts for controllers;
- an MPC or optimal-control adapter;
- a consistent control and replay interface for rule-based and advanced controllers; and
- optionally, a simple validated zone thermal model.

These extensions should live in OEL's reusable library boundaries and be tested independently of
the final case study.

## Evaluation of OEL for the e-Energy Full Paper

The paper needs evidence beyond an architecture diagram, API coverage, and successful notebooks.
It must show that the common environment enables a fair multi-market comparison and that evaluation
choices can materially affect the conclusions.

### Physical and semantic validity

- electric-energy conservation;
- grid and battery energy balance under simultaneous service requests;
- battery state bounds;
- product-compatible units, signs, time grids, and commitment intervals;
- explicit clipping, priority, conflict, and non-delivery accounting; and
- settlement computed from common realized replay rather than strategy-owned estimates.

### Data and source validity

- immutable source requests, normalized artifacts, content digests, and source versions;
- explicit UTC and local-market time interpretation;
- no silent conversion of control-area observations into asset dispatch;
- documented acquisition requirements and redistribution restrictions; and
- a clear distinction between observed data, scenario proxies, and derived simulations.

### Reproducibility

- canonical experiment manifests;
- immutable or integrity-checked source artifacts;
- code and schema versions;
- declared information cutoffs, strategy configuration, and solver policy;
- identical replay from the same experiment bundle; and
- output fingerprints or evidence identities where appropriate.

### Comparative stability

- strategy rankings across delivery periods and activation conditions;
- uncertainty intervals for physical and settlement differences;
- sensitivity to state carry-over, acceptance, conflict, and allocation assumptions;
- comparison of planning-objective and realized-evaluation rankings; and
- transparent reporting when a conclusion is not stable.

### Composability and extensibility

- the same real-data bundle and evaluator used with all strategy classes;
- isolated, sequential, and joint strategies emitting one commitment contract;
- product-specific activation and settlement composed without erasing service semantics; and
- no duplication of battery physics or settlement inside strategy or notebook code.

## Paper and artifact scope

### ACM e-Energy Full Paper

The e-Energy paper should focus on:

- real-data producers and immutable artifacts in `open_energy_lab.market`;
- heuristic, isolated, sequential, robust, and joint strategies in `open_energy_lab.control`;
- common battery replay, multi-service delivery, settlement, and evaluation in
  `open_energy_lab.simulator`;
- visualization, reporting, failure records, and evidence identities; and
- the experiment-composition and causality contracts connecting those areas.

TPM investment planning and the district-cooling resilience results should be omitted from the
paper's evaluation and contribution claims. TPM-generated market strategies can remain future
consumers of the published evaluation environment.

For the paper to provide meaningful visibility to OEL, its artifact should be a public,
market-focused release containing:

- a redistribution-safe repository or release branch;
- redistribution-safe example inputs plus documented acquisition for restricted or credentialed
  market inputs;
- an explicit software license;
- `CITATION.cff`;
- a versioned release tag;
- an archived DOI, for example through Zenodo;
- installation and quickstart documentation;
- executable multi-market study manifests; and
- a documented boundary between observed market data, proxies, derived asset scenarios, and
  synthetic stress tests.

### BS2027 paper

The BS manuscript may use the same public OEL release, but its contribution and evaluation should
focus on the new district-cooling system, disturbance protocol, controllers, and resilience
findings. General OEL architecture and platform comparisons should be limited to what is needed to
make the study reproducible. TPM planning and market bidding remain outside its scope.

## Expected paper structures

### ACM e-Energy Full Paper

1. **Problem:** multi-market strategies are difficult to compare when each study owns its data,
   information assumptions, physics, and settlement.
2. **Related platforms:** market simulators, ancillary-service studies, optimization packages, and
   learning environments.
3. **OEL architecture:** real-data artifacts, information cutoffs, strategy producers, accepted
   commitments, common physical replay, settlement, and evidence.
4. **Market and asset model:** energy, FCR, aFRR, mFRR, battery constraints, observed inputs, and
   derived-scenario assumptions.
5. **Strategies:** heuristic, isolated, sequential, robust-FCR benchmark, and joint optimization.
6. **Evaluation:** planning versus realized outcomes, physical delivery, settlement, multi-day state,
   and comparative stability.
7. **Reproducibility and limitations:** artifact identities, acquisition workflow, source semantics,
   unsupported asset-level claims, and current market coverage.

### BS2027 Research Paper

1. **Problem:** cooling-service resilience under heat and compound infrastructure disruptions.
2. **System and assumptions:** hybrid district/local cooling, storage, fixed capacities, and service
   availability.
3. **Controllers:** rule-based, perfect-forecast reference, and forecast-limited anticipatory
   control.
4. **Scenario protocol:** independent disturbances, restoration uncertainty, and forecast error.
5. **Results:** resilience, recovery, energy, peak, and cost distributions.
6. **Sensitivity and limitations:** regimes where anticipatory control helps, does not help, or
   fails.
7. **Reproducibility:** OEL experiment bundle and evidence, without re-arguing the platform paper.

## Immediate submission decisions

### BS2027 abstract

The abstract should commit to these boundaries:

- District-cooling resilience is the principal contribution; OEL is enabling infrastructure.
- Physical capacities are fixed; there is no investment sizing.
- Scenario definitions are independent of controller outcomes.
- Rule-based and anticipatory controllers share one replay and metric contract.
- Synthetic conclusions remain conditional on declared assumptions.
- Expected findings concern when anticipatory control helps or fails, not a guaranteed resilience
  improvement.

### ACM e-Energy Full Paper

The paper should commit to these boundaries:

- OEL's causal, producer-neutral multi-market evaluation environment is the principal contribution.
- Real-data integration, common battery replay, product-specific settlement, and evidence provenance
  are part of the evaluated system.
- The robust FCR method is a showcased benchmark strategy, not an algorithmic novelty claim.
- The strategy comparison includes isolated, sequential, and joint participation under identical
  data and evaluation assumptions.
- TPM investment planning and district-cooling resilience are outside the manuscript.
- Any claim that comparable libraries do not exist must be supported by a structured review.

## Schedule and decision gates

| Date | Deliverable or decision |
| --- | --- |
| 1 September 2026 | Submit a BS abstract centred on district-cooling resilience. |
| September 2026 | Do not rush an archival e-Energy Note; freeze the Full Paper's market, strategy, data, and evaluation scope. |
| September-December 2026 | Complete the multi-market evaluator and comparison while independently implementing and running the BS district-cooling study. |
| 15 January 2027 | Submit the BS full paper. |
| January 2027 | Target the e-Energy Winter Full Paper if the multi-day strategy comparison and reproducible artifact are complete; exact deadline pending. |

The e-Energy policy prohibits simultaneous submissions. The two manuscripts must therefore remain
substantively distinct in question, evaluation, results, figures, and claims. If the platform and
district-cooling work cannot be separated cleanly, one venue should be selected rather than
submitting overlapping work. The Winter paper should be attempted only if its evidence is complete;
the deadline should not determine the results presented.

## Sources discussed

- [BS2027 submission page](https://bs2027.org/submissions/)
- [BS2027 Guidelines for Authors](https://bs2027.org/wp-content/uploads/2026/08/bs2027-guidelines-for-authors-final.pdf)
- [ACM e-Energy 2027 Call for Papers](https://energy.acm.org/conferences/eenergy/2027/pages/cfp.php)
- [ACM e-Energy 2027 Fall submission site](https://eenergy27fall.hotcrp.com/)
- [ACM e-Energy 2027 Winter submission site](https://eenergy27winter.hotcrp.com/)
- [OEL bidder-neutral FCR evaluation plan](../specs/012-fcr-bid-evaluation-parity/plan.md)
- [OEL reference robust FCR bidding plan](../specs/013-reference-robust-fcr-bidding/plan.md)
- [OEL causal rolling FCR backtest plan](../specs/015-fcr-rolling-backtest-parity/plan.md)
- [OEL RTE aFRR/mFRR source and scenario contract](../docs/architecture/rte-balancing-energy.md)
- [CityLearn repository](https://github.com/intelligent-environments-lab/CityLearn)
- [CityLearn: Standardizing Research in Multi-Agent Reinforcement Learning for Demand Response and Urban Energy Management](https://arxiv.org/abs/2012.10504)
- [BOPTEST project](https://ibpsa.github.io/project1-boptest/index.html)
- [Building Optimization Testing Framework for Simulation-Based Benchmarking of Control Strategies in Buildings](https://escholarship.org/uc/item/7xb9g6hv)
- [IBPSA Project 2 BOPTEST overview at Building Simulation 2025](https://publications.ibpsa.org/conference/paper/?id=bs2025_1666)
- [Sinergym documentation](https://ugr-sail.github.io/sinergym/compilation/v2.5.0/index.html)
- [Virtual Testbed for Model Predictive Control Development in District Cooling Systems](https://www.sciencedirect.com/science/article/pii/S1364032120302112)
- [Coordinating Multi-Energy Stations for Climate-Resilient District Cooling](https://www.sciencedirect.com/science/article/pii/S0360544226004445)
