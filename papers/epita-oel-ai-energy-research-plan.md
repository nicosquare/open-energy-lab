# EPITA hosting research plan: AI for energy decision-making with Open Energy Lab

**Discussion date:** 2026-09-01  
**Status:** Working concept for discussion; not yet a formal hosting proposal  
**Possible host institution:** EPITA Research Laboratory (LRE), Paris  
**Scientific contact:** Éric Moulines; initial discussions are underway  
**Expected format:** A research visit of approximately four to six weeks, subject to confirmation

## Core recommendation

The proposal should present one coherent research programme rather than a catalogue of unrelated
applications. A useful umbrella is:

> **AI for energy decision-making across timescales: probabilistic planning, flexibility control,
> and market participation with Open Energy Lab**

Possible French title:

> **IA pour la décision dans les systèmes énergétiques : planification probabiliste, pilotage de
> la flexibilité et participation aux marchés avec Open Energy Lab**

The central scientific question would be:

> How can uncertainty-aware AI methods support consistent investment, control, and market
> decisions while respecting physical constraints and allowing reproducible comparison?

Open Energy Lab (OEL) is the common experimental backbone. It is not, by itself, the research
question. Its role is to connect scenarios, uncertainty models, physical simulation, optimization,
control, market data, and evaluation so that methods can be compared under common assumptions.

The research plan should have two layers:

1. **A longer-term programme** containing the three connected research axes below.
2. **One bounded project for the EPITA visit**, selected with the host and designed to yield a
   concrete method, experiment, and joint output within a few weeks.

Trying to execute all three axes during one short visit would weaken the proposal. The broader
programme establishes continuity; the visit project makes the convention credible. Based on the
initial discussion with Éric Moulines, the focal project should be distributed control of
heterogeneous building microgrids through a hybrid MPC–RL architecture, with aggregator-level
flexibility and ancillary-service participation as the connection to OEL's market research.

## Motivation

Energy decisions occur at very different horizons. Investment choices are made over years, asset
control over minutes or hours, and market commitments over product-specific intervals. Yet these
problems share several methodological difficulties:

- uncertain weather, demand, prices, and service activation;
- physical and operational constraints that cannot be ignored by a learned model;
- a need to combine statistical learning with mathematical optimization;
- limited access to operational data; and
- experimental results that are hard to compare when every study constructs its own scenarios,
  simulation logic, and performance measures.

OEL is intended to address the experimental fragmentation without claiming that one library solves
all energy problems. It provides reusable building blocks for creating physically reasonable
synthetic scenarios, importing available real data, producing decisions with different classes of
methods, replaying those decisions through common physical models, and retaining the evidence
needed to reproduce the comparison.

The research hypothesis is therefore both scientific and infrastructural:

> Better uncertainty representations and learning-based decision methods can improve energy
> planning and operation, but their value can only be established through common, physically
> consistent, and reproducible evaluation.

## Research trajectory and the purpose of OEL

OEL should be presented as an intentional consolidation of a research trajectory, not as a library
created first and justified through applications afterwards. Nicolas began actively developing OEL
to bring together methods, models, and experimental practices that had emerged across his PhD work
and that would otherwise remain in separate paper-specific codebases.

### Work preceding OEL

Two research lines precede the unified library:

1. **Microgrid management using RL and federated RL.** This work established an interest in
   distributed learning and control, heterogeneous energy systems, local information, and
   coordination without requiring all data or decisions to be centralized.
2. **Investment planning using tractable probabilistic models.** The manuscript
   [*Tractable Probabilistic Models for Investment
   Planning*](https://arxiv.org/abs/2511.13888), currently under review at *IEEE Transactions on
   Power Systems*, uses sum-product networks to represent high-dimensional uncertainty and embed
   probabilistic reliability requirements in mixed-integer investment planning.

There is also relevant adjacent work: [*WattCouncil: Context-Aware Household Energy Scenario
Generation With Governed LLMs*](https://doi.org/10.1145/3744256.3812595), published at ACM BuildSys
2026. WattCouncil uses governed LLM agents to generate and audit context-sensitive household-energy
scenarios under cultural, temporal, and physical constraints, and evaluates the generated profiles
against the CER household dataset. This work is not a principal methodological axis of the proposed
EPITA visit, but it demonstrates prior work on the energy-data accessibility problem that also
motivates OEL.

These are not disconnected projects. They provide two methodological foundations for the broader
programme:

- learning and distributed control for operational decisions; and
- probabilistic representation and optimization for decisions under uncertainty.

OEL supplies the missing common layer: reusable weather and demand artifacts, physical simulation,
planning and control interfaces, market observations, strategy-neutral evaluation, provenance,
and reproducible experiments. The intention is not to migrate every historical implementation
unchanged, but to extract validated and reusable behavior that can support multiple new studies.

### Possible WattCouncil integration boundary

WattCouncil could become an optional upstream scenario producer or adapter for OEL rather than a
core dependency:

```text
WattCouncil household context and generated demand
                         |
                         v
         optional OEL validation/provenance adapter
                         |
                         v
       versioned synthetic demand scenario artifact
                         |
                         v
       microgrid simulation and control experiments
```

Its immediate use would be to create diverse household routines, base-load profiles, contextual
conditions, or population mixtures for heterogeneous microgrid experiments. Generated data should
remain explicitly labeled as synthetic and retain the model, prompt or governance configuration,
validation evidence, and artifact provenance required to reproduce it.

This integration has a clear limit. Household demand profiles alone do not define controllable
building dynamics, HVAC flexibility, comfort states, response speed, or rebound. Those properties
must remain simulator- and control-model responsibilities in OEL. WattCouncil would enrich the
scenario distribution; it would not establish that an aggregated fleet can deliver an ancillary
service. Keeping that boundary explicit allows the published work to strengthen the programme
without pulling the EPITA plan toward LLM research.

### Near-term consolidation around three application lines

Over the coming months, OEL development should be organized around three concrete research lines:

| Research line | Near-term scientific objective | Principal OEL capabilities to consolidate |
| --- | --- | --- |
| Heterogeneous microgrids and market participation | Use distributed hybrid MPC–RL control to stabilize aggregate building flexibility and make it dependable for ancillary-service participation | Building and asset composition, distributed controller interfaces, aggregation, flexibility envelopes, activation tracking, and market handoff |
| BESS participation in ancillary services | Compare single-market, sequential, and multi-market strategies using common real data, physical replay, and settlement | Market artifacts, information cutoffs, commitment interfaces, BESS replay, degradation, settlement, and multi-day backtesting |
| District-cooling demand flexibility | Determine how thermal storage and predictive control can reduce operating cost and expose reliable demand flexibility in Gulf conditions | Cooling-load scenarios, plant and chilled-water storage models, tariffs, threshold/MPC/learned controllers, and resilience or demand-response evaluation |

The TPM investment-planning line remains part of the long-term research programme and OEL
architecture, but it is already represented by a paper under review. It should therefore be
described as prior and ongoing work rather than counted as one of the three new application papers.
Future probabilistic-planning studies must contribute a distinct question rather than repeat the
current manuscript.

This distinction gives the programme two complementary structures:

- **Scientific horizons:** investment, operational control, and market decisions.
- **Near-term studies:** aggregated microgrids, BESS market participation, and district cooling.

The microgrid project deliberately spans the latter two scientific horizons. Its controller must
first make distributed flexibility dependable; the market layer can then decide how much of that
flexibility to commit.

## Provisional publication portfolio

Venues should be selected after the scientific contribution of each study is fixed, rather than
designing studies only to match a target outlet. Nevertheless, the following portfolio shows that
the three OEL research lines connect to established power-systems, energy, computing, and building
communities.

| Research output | Most natural venue families | Candidate venues |
| --- | --- | --- |
| Distributed hybrid MPC–RL for heterogeneous microgrids, with reliable grid-service tracking | Power-system control and computing-energy | *IEEE Transactions on Power Systems*, PSCC, ACM e-Energy |
| Computing and coordination mechanisms for heterogeneous building aggregation | Computing-buildings and computing-energy | ACM BuildSys, ACM e-Energy |
| BESS single- and multi-market ancillary-service participation | Power-system operation, energy optimization, and computing-energy | *IEEE Transactions on Power Systems*, PSCC, *Applied Energy*, ACM e-Energy |
| District-cooling thermal storage, control, and demand flexibility | Building energy, building science, and building simulation | *Energy and Buildings*, *Building and Environment*, ACM BuildSys, IBPSA Building Simulation, *Journal of Building Performance Simulation*, *Applied Energy* |
| OEL simulation, evaluation, or reproducibility method, once demonstrated across sufficiently complete studies | Computing-energy or simulation methodology | ACM e-Energy, *Journal of Building Performance Simulation* |

The intended roles and currently known submission windows of the candidate venues are shown below.
Deadlines were checked on **1 September 2026** and should be rechecked before planning a submission.
“Rolling” means that the regular journal accepts manuscripts continuously; individual special
issues may have separate deadlines. A conference whose next call is not published is marked “TBA,”
not rolling.

| Venue | Type | Main community | Strongest fit within this programme | Next submission deadline or status |
| --- | --- | --- | --- | --- |
| [*IEEE Transactions on Power Systems*](https://ieee-pes.org/publications/transactions-on-power-systems/) | Journal | Power systems | Grid operation, optimization, flexibility, uncertainty, and control | Rolling regular submissions |
| [PSCC 2028](https://pscc2028.nl/) | Biennial conference | Power systems | Power-system optimization, control, markets, uncertainty, and ML | Paper deadline TBA; conference 26–30 June 2028 |
| [*Applied Energy*](https://www.sciencedirect.com/journal/applied-energy) | Journal | Energy systems | Storage, flexibility, energy optimization, and applied AI or control | Rolling regular submissions |
| [*Energy and Buildings*](https://www.sciencedirect.com/journal/energy-and-buildings) | Journal | Building energy | HVAC, thermal storage, building flexibility, and control | Rolling regular submissions |
| [*Building and Environment*](https://www.sciencedirect.com/journal/building-and-environment) | Journal | Building science | Building performance, thermal conditions, comfort, HVAC, and controls | Rolling regular submissions |
| [ACM e-Energy 2027](https://energy.acm.org/conferences/eenergy/2027/pages/cfp.php) | Conference | Computing and energy | ML/RL, optimization, energy markets, and grid control | Fall: registration 11 September 2026; paper 18 September 2026, both AoE. Winter dates TBA |
| [ACM BuildSys 2027](https://buildsys.acm.org/2027/) | Conference | Computing and buildings | Smart buildings, HVAC control, distributed intelligence, ML/RL, and sensing | Paper deadline TBA; co-located event announced for 5–11 June 2027 |
| [IBPSA Building Simulation 2027](https://bs2027.org/) | Biennial conference | Building-performance simulation | Simulation, controls, HVAC, district energy, and flexibility | Abstract 1 September 2026, 23:59:59 CEST; full paper 15 January 2027 after abstract acceptance |
| [*Journal of Building Performance Simulation*](https://www.tandfonline.com/journals/tbps20/about-this-journal) | Journal | Building-performance simulation | Simulation methods, validation, uncertainty, and control | Rolling regular submissions; relevant [“Control Technologies for Buildings” special issue](https://think.taylorandfrancis.com/special_issues/innovation-implementation-control-technologies-buildings/): 31 May 2027 |

### Near-term deadline view

| Date | Venue and action | Relevance |
| --- | --- | --- |
| **1 September 2026** | BS2027 abstract submission | District-cooling thermal-storage study |
| **11 September 2026 (AoE)** | ACM e-Energy 2027 fall paper registration | OEL/BESS multi-market study |
| **18 September 2026 (AoE)** | ACM e-Energy 2027 fall full-paper submission | OEL/BESS multi-market study; only realistic if the evidence is already sufficiently mature |
| **15 January 2027** | BS2027 full paper | Applies after abstract acceptance |
| **31 May 2027** | JBPS special issue, “Control Technologies for Buildings” | Potentially relevant to building aggregation, hybrid control, or district cooling |

The e-Energy winter cycle, BuildSys 2027, and PSCC 2028 should remain calendar watch items until
their official submission dates are published. The rolling journals provide fallback timing, but
venue choice should still follow the completed contribution rather than the earliest available
submission route.

This is a portfolio, not a commitment to submit the same work repeatedly. Each paper should own a
distinct scientific question, and any shared OEL material should be treated as common
infrastructure rather than recycled novelty. In particular:

- the microgrid paper should contribute the hybrid distributed-control and reliability method;
- the BESS paper should contribute the common multi-market comparison and its empirical findings;
- the district-cooling paper should contribute findings about thermal-storage operation and
  flexibility; and
- a library or methods paper should only be pursued once OEL has enough demonstrated breadth and
  evidence to support claims beyond one application.

## The three research axes

### Axis 1 — Investment planning using probabilistic models

**Question.** How can structured probabilistic models represent dependencies between weather,
demand, outages, and system performance, and how can this information be embedded efficiently in
investment decisions?

**Methods.** Tractable probabilistic models, probabilistic circuits or sum-product networks,
conditional probability queries, uncertainty quantification, and mixed-integer optimization.

**OEL role.** Produce versioned weather-demand-system scenarios; fit and persist probabilistic
artifacts; expose conditional risk expressions; and connect them to solver-owned planning models.

**Research direction.** The TPM investment-planning paper under review is the starting foundation,
not a proposed duplicate. Follow-up work could examine composable conditional-risk interfaces,
different probabilistic representations, decision sensitivity to model fidelity, or planning under
aggregated flexibility. Any visit proposal should distinguish these questions explicitly from the
claims already under review.

### Axis 2 — Flexibility through control

**Question.** When do predictive or learned controllers convert flexible energy assets into useful
system-level flexibility while preserving service quality and physical feasibility?

Two motivating cases are:

- **microgrid aggregation**, where heterogeneous buildings retain local operational constraints
  while an aggregator coordinates their collective response; and
- **district cooling with chilled-water thermal storage**, comparing current threshold-style
  operation with model predictive control and fast surrogate policies.

**Methods.** Model predictive control, approximate dynamic programming, reinforcement learning,
surrogate-policy learning, constrained learning, uncertainty-aware control, and interpretable or
verifiable policies.

**OEL role.** Supply weather-conditioned demand, heterogeneous building and asset models, local and
aggregator controller interfaces, counterfactual replay, and common metrics for cost, comfort,
service quality, peaks, rebound, response duration, and constraint violations.

**Initial microgrid-aggregation study.** Each building would have different demand, thermal
dynamics, controllable equipment, local storage, comfort constraints, and forecast quality. Local
and aggregator MPC components would use explicit models to plan accurate trajectories, enforce
physical and service constraints, follow aggregate requests, and manage recovery after activation.
RL would complement this model-based backbone where models and forecasts are imperfect or where
centralized optimization and hand-designed coordination do not scale. It might learn model-error
corrections, coordination signals, MPC parameters or terminal values, or residual actions. The
scientific problem is to determine which MPC–RL coupling makes the distributed system precise,
adaptive, scalable, and capable of generalizing to heterogeneous or previously unseen building
fleets.

The aggregation may expose a storage-like interface to the market layer, but it should not be
treated as a literal large battery. Building flexibility is time-varying, state-dependent,
asymmetric between upward and downward response, affected by comfort and local objectives, and
subject to rebound. These are not merely limitations: they define the control problem. The aim is
to stabilize this heterogeneous response, maintain sufficient reserve margin, and expose a
conservative but useful service envelope whose response time, duration, tracking accuracy,
availability, and recovery behavior are reliable enough for a selected ancillary-service product.
Quantifying the residual uncertainty and its consequences for commitments and non-delivery is part
of the research contribution.

**Complementary district-cooling study.** A plant-inspired Gulf case remains especially tangible.
Cooling is a major component of electricity demand in the hottest months, district-cooling plants
are common, and many include large chilled-water tanks. The study would compare a transparent
threshold policy with perfect-information bounds, MPC, and a computationally cheaper learned
surrogate. It would
measure plant efficiency and cost, including kW/RT and \$/RT-hour, as well as the magnitude,
duration, reliability, and rebound of the flexibility offered to the grid. Resilience should be
claimed only if the experiments include an explicit stressor—such as extreme heat, a peak-power
limit, or a demand-response event—and demonstrate maintained cooling service.

### Axis 3 — Market participation by storage and aggregated resources

**Question.** How should a BESS or aggregated microgrid allocate limited energy and power across
energy and ancillary-service markets under uncertain prices and activation?

**Methods.** Deterministic, stochastic, and robust optimization; forecast-then-optimize and
decision-focused learning; sequential and joint allocation; risk-aware bidding; and possibly
learned bidding policies.

**OEL role.** Provide real-data acquisition and immutable offline artifacts, explicit information
cutoffs, replaceable strategy interfaces, common physical replay, service-specific settlement, and
multi-day state carry-over. This enables fair comparisons between heuristic, isolated
single-market, sequential, robust, and jointly optimized strategies.

**Novelty boundary.** OEL need not claim to have invented robust bidding. The interesting research
is whether different market strategies reach the same conclusions when evaluated with identical
data, accepted commitments, activation, battery physics, and settlement. The unified multi-market
commitment and evaluation layer is still a research-development objective and should not be
described as already complete.

## A common methodological spine

The three axes can be presented as decisions at different timescales rather than three unrelated
projects:

| Horizon | Decision | Main uncertainty | Candidate AI contribution | OEL evidence |
| --- | --- | --- | --- | --- |
| Strategic | What capacity should be built? | Long-term weather, demand, outages | Probabilistic inference embedded in optimization | Risk, cost, capacity, sensitivity |
| Operational | How should flexible assets be controlled? | Forecast error, state, disturbances | Predictive or learned constrained policies | Cost, service, flexibility, violations |
| Market | What should be committed to which product? | Prices, acceptance, activation | Robust or decision-focused allocation | Delivery, settlement, degradation, risk |

Across all three horizons, the recurring workflow is:

```text
real or physically grounded scenario artifacts
                    |
                    v
       uncertainty representation
                    |
                    v
 optimization, controller, or learned policy
                    |
                    v
       common constrained physical replay
                    |
                    v
       metrics, provenance, and comparison
```

This is the strongest justification for building OEL: each paper can contribute a new scientific
method or domain finding without rebuilding the complete experimental environment, while common
interfaces make cross-method conclusions more defensible.

## Recommended focal project for the EPITA visit

### Preferred option: Distributed flexibility from heterogeneous buildings with hybrid MPC–RL

Suggested project title:

> **Distributed control of heterogeneous building microgrids with hybrid MPC–RL for energy
> flexibility and ancillary services**

Possible French title:

> **Pilotage distribué de micro-réseaux de bâtiments hétérogènes par une approche hybride MPC–RL
> pour la flexibilité énergétique et les services système**

This reflects the methodological direction identified in the initial discussions with Éric
Moulines. The project would investigate a distributed architecture in which MPC and RL jointly
control the aggregation rather than assigning all intelligence to RL and leaving MPC only as a
comfort or safety filter:

```text
market commitment or grid flexibility request
                       |
                       v
        hybrid MPC–RL aggregator/coordinator
       (planning, allocation, adaptation, tracking)
          |            |            |
          v            v            v
     local hybrid  local hybrid  local hybrid
     controller A  controller B  controller C
          |            |            |
          +------------+------------+
                       |
                       v
 stabilized aggregate delivery and qualification evidence
```

MPC is the model-based component for forecasting trajectories, coordinating constrained actions,
tracking activation accurately, protecting physical and comfort limits, and anticipating rebound.
RL is introduced precisely because model-based control may be inaccurate under model mismatch and
uncertain behavior, and because a purely optimized distributed scheme may become computationally
or communicationally difficult at scale. Conversely, pure RL may be sample-inefficient, imprecise,
or unreliable in operating regions poorly represented during training.

The research should therefore compare a small number of genuine coupling patterns rather than
presuppose one:

1. **MPC-led hybrid:** MPC produces the constrained decision while RL learns model-error
   corrections, parameter adaptation, terminal values, or bounded residual actions.
2. **RL-led hybrid:** RL proposes allocations or references and MPC corrects them through
   constrained planning before execution.
3. **Hierarchical hybrid:** RL coordinates the slower aggregator-level allocation while
   distributed MPC performs fast local planning and tracking.

The first pattern is a sensible starting point when precision and service reliability are the
motivation for retaining MPC. The alternatives make the architectural choice an experimental
question rather than an assumption.

The central hypothesis is:

> A distributed hybrid MPC–RL controller can stabilize the uncertain, state-dependent flexibility
> of heterogeneous buildings into a more reliable ancillary-service resource: MPC supplies
> constrained predictive precision, while RL adapts to modeling errors, uncertainty, and
> coordination complexity.

Candidate research questions include:

1. What information must buildings share for effective coordination, and what can remain local?
2. Which quantities should MPC calculate and which model errors, policies, residuals, or value
   functions should RL learn?
3. Which coupling pattern gives the best trade-off between tracking precision, constraint
   satisfaction, adaptation, and runtime?
4. How can the controller transform a time-dependent upward and downward flexibility envelope,
   including recovery and rebound, into a firm service offer with an explicit confidence level?
5. Can the hybrid controller scale and generalize to different numbers and mixtures of buildings
   without retraining from scratch?
6. How do forecast errors, communication limits, unavailable buildings, and distribution shift
   affect ancillary-service qualification and delivery reliability?
7. How should residual flexibility uncertainty influence market commitments and non-delivery risk?

The evaluation should compare at least:

- uncoordinated local or threshold-based control;
- price-based coordination or another transparent aggregator heuristic;
- centralized MPC as a small-fleet performance reference, where computationally possible;
- distributed or hierarchical MPC;
- pure RL, where it is a meaningful baseline; and
- the selected MPC-led, RL-led, or hierarchical hybrid architecture.

Relevant metrics include operating cost, comfort or service violations, peak demand, tracking
error, upward and downward response, recovery and rebound, communication requirements, controller
runtime, scalability, performance on unseen building mixtures, response time, sustained-delivery
duration, availability, product-qualification rate, ancillary-service revenue, and non-delivery
penalties.

### Relationship to market participation

The connection to OEL's BESS market work should be explicit but staged:

1. **Control layer:** stabilize the response so that the distributed building fleet can follow an
   aggregate power request accurately while preserving local constraints.
2. **Flexibility layer:** turn the state-dependent response into a conservative firm envelope with
   declared response time, duration, recovery cost, and uncertainty rather than assigning a fixed
   virtual-battery capacity.
3. **Market layer:** allow a single- or multi-market strategy to make commitments against that
   envelope and evaluate realized activation, product-specific qualification criteria, delivery,
   settlement, and penalties through OEL.

This creates a reusable interface between distributed control and market participation. A BESS and
a building aggregation could then be evaluated through related commitment and settlement
contracts, while retaining their different physical dynamics. Full multi-market optimization is a
natural follow-up, not a dependency for proving the core distributed-control contribution during
the visit.

### Alternative A: Probabilistic decision models for energy planning and control

This option would study efficient uncertainty representations, conditional inference, or
stochastic approximation at the interface between probabilistic models and constrained decisions.
It fits the broader programme well, but the precise question must be separated from the TPM paper
already under review. It is most credible if the collaboration identifies a genuinely new
methodological problem before the visit.

### Alternative B: District-cooling surrogate control

This option retains the earlier idea of learning a fast, constraint-aware surrogate from MPC or an
offline optimizer for chilled-water thermal storage. It remains a strong application and potential
second case study, but the distributed heterogeneous-building problem now provides the clearer
primary connection to Éric's interests.

## France as the initial market-data implementation context

OEL is intended to be source- and country-extensible, but its first working market-facing version
has a concrete geographical foundation. France has made substantial electricity-system and market
information available through public data portals and APIs. RTE's [public API
portfolio](https://www.services-rte.com/files/live/sites/services-rte/files/API%20acteurs%20de%20march%C3%A9%20RE-AA-RR-GRD%20Version%20publique%202024-02-27.pdf)
includes national production, consumption, balancing, capacity-mechanism, and cross-border
information, although access to individual APIs can still require registration and credentials.
This openness made the French system a practical place to build and test OEL's first real-data
contracts instead of beginning with wholly synthetic market traces.

The current OEL foundation includes a direct adapter for the **RTE Balancing Energy API v5.2** and
immutable artifact contracts for French aFRR and mFRR observations. It preserves product,
direction, units, 15-minute intervals, UTC and Europe/Paris time interpretation, source fields,
request provenance, and content fingerprints. These restoration-service components sit beside the
existing French-context day-ahead and FCR bidding, physical replay, settlement, and rolling-study
work.

The design principle is:

> **France-specific first, source-independent by design.**

Source-specific acquisition belongs at the edge of OEL. Once acquired, data is transformed into
canonical, source-independent artifacts and product contracts so that simulators, controllers,
bidders, and evaluators do not depend directly on an RTE response format. This creates a credible
path toward other European or international data sources without pretending that products,
settlement, or qualification rules are identical across markets.

This French foundation strengthens the relevance of an EPITA collaboration in several ways:

1. It gives the visit a locally grounded energy-system context rather than a generic AI case.
2. It connects EPITA's methodological contribution to an existing French data and flexibility
   ecosystem.
3. It creates a natural demonstration path from distributed building control to a French
   ancillary-service use case with explicit response and delivery requirements.
4. It enables a longer-term portability question: which parts of flexibility characterization,
   bidding, physical replay, and evidence are universal, and which must remain product- or
   system-operator-specific?

The boundary must remain explicit. Public RTE aFRR and mFRR records are French control-area
observations, not the high-frequency command sent to an individual BESS or building aggregator.
OEL may use them as market context or as inputs to an explicitly labeled derived simulation, but
they do not by themselves demonstrate historical asset dispatch, commercial settlement, or formal
qualification. Similarly, open access does not automatically grant unrestricted redistribution;
credentials, attribution, licensing, and data-retention terms remain part of the artifact contract.

## Why EPITA is a plausible host

The institutional fit is primarily methodological, not based on an identified EPITA energy-systems
laboratory. The [EPITA Research Laboratory](https://www.epita.fr/en/research-at-epita/) includes an
Artificial Intelligence team, and the LRE describes that team's work in representation learning,
optimization, and data mining. Its [Machine Learning and Applications
axis](https://www.lre.epita.fr/axes/machine-learning-and-applications/) also lists reinforcement
learning and constraint-based programming, while its [computation
platform](https://www.lre.epita.fr/platforms/computation) explicitly supports controlled,
reproducible experiments. OEL would contribute the energy domain, constrained simulators, data
contracts, and benchmark questions.

Relevant interlocutors include:

- **Éric Moulines, Paris.** Initial discussions with him have identified distributed microgrid
  control through hybrid MPC–RL as a promising common research direction. He is listed as an EPITA
  AI professor in Paris and is also at MBZUAI.
  His work in probabilistic machine learning, uncertainty quantification, stochastic optimization,
  time-series methods, and control of complex systems makes him the clearest bridge for the
  programme, particularly its probabilistic, distributed, and constrained-decision aspects
  ([EPITA profile](https://www.lre.epita.fr/members/eric-moulines/), [MBZUAI
  profile](https://mbzuai.ac.ae/study/faculty/professor-eric-moulines/)).
- **Marc Plantevit, Lyon.** He leads EPITA's AI team and has already co-authored work on
  reproducible electricity-price forecasting and differentiable optimization of European market
  clearing. He is a particularly relevant scientific contact for the market-participation axis,
  even if the physical stay is based in Paris ([profile](https://www.lre.epita.fr/members/marc-plantevit/),
  [decision-focused electricity-market paper](https://www.lre.epita.fr/dload/papers/tschora.23.dsaa.pdf)).
- **Thierry Géraud.** As EPITA's research director, he may be the appropriate institutional contact
  once a scientific sponsor and project have been identified; the scientific discussion should
  come first ([LRE members and leadership](https://www.lre.epita.fr/the-lab)).

A useful collaboration model would be: an EPITA researcher contributes the AI question and method;
Nicolas contributes the energy-system formulation and OEL testbed; both parties define the
evaluation protocol and resulting publication together.

## Proposed four-to-six-week work plan

The plan should be modular so that the first four weeks form a complete core and weeks five and six
strengthen the research output.

### Before arrival

- Agree on one focal question, one case study, and one primary EPITA scientific contact.
- Define a small but meaningfully heterogeneous building fleet and the assets available to each
  local controller.
- Freeze an OEL scenario bundle, local-control baselines, metrics, and expected data access.
- Prepare a reproducible environment and a two-page method note.
- Identify which components already exist and which must be implemented during the visit.

### Week 1 — Joint formulation

- Present OEL and the three-axis programme in an LRE seminar or working session.
- Refine the distributed-control hypothesis and select the MPC–RL coupling patterns to compare
  with the host.
- Define baselines, information available to each policy, feasibility criteria, and evaluation
  splits before inspecting comparative results.

### Week 2 — Method and experiment contract

- Implement the building-to-aggregator information, request, response, and evidence interfaces.
- Establish uncoordinated, heuristic, pure MPC, and, where meaningful, pure-RL baselines.
- Freeze stress scenarios, ablations, metrics, seeds, and artifact provenance.

### Weeks 3–4 — Prototype and core evidence

- Train the aggregator policy and solve the MPC components.
- Replay all policies through the same OEL physical model.
- Analyze performance, local feasibility, communication, scalability, and failure cases.
- Produce a reproducible core experiment and decide whether the result supports a paper.

### Weeks 5–6 — Extension, writing, and continuation

- Run sensitivity and out-of-distribution experiments on different building mixtures, forecasts,
  and communication conditions.
- Connect the aggregate flexibility interface to one bounded ancillary-service case if the core
  controller is sufficiently mature.
- Draft the method and experiment sections of a joint paper or technical report.
- Define a follow-up publication, student project, joint grant, or longer collaboration.
- Present results and leave a reviewed OEL contribution with documentation and tests.

## Expected outputs

A realistic visit would target:

1. a jointly agreed research question and evaluation protocol;
2. one reusable OEL method adapter, controller, or benchmark component;
3. one reproducible experiment bundle with explicit provenance;
4. a manuscript outline or technical report with preliminary evidence;
5. one research seminar or internal presentation at EPITA; and
6. a post-visit roadmap covering a paper, student supervision, or funding opportunity.

The proposal should not promise three completed papers in several weeks. A stronger commitment is
one working research artifact and one credible joint publication path, situated within the wider
three-axis programme.

## Suggested structure of the formal research plan

A two-to-four-page document for the convention could use this order:

1. **Title, applicant, proposed host, location, dates, and duration**
2. **Scientific context and problem** — energy decisions across timescales and fragmented
   experimental practice
3. **Prior work and available foundation** — OEL, the TPM paper under review, and implemented
   market/control components
4. **Overall objective and research questions** — the common programme and its three axes
5. **Focal objective of the EPITA visit** — one method and one case, stated as a testable question
6. **Methodology** — scenarios, models, baselines, common replay, metrics, and validation
7. **Work plan and milestones** — pre-visit plus four-to-six-week schedule
8. **Expected scientific and software outputs**
9. **Fit and mutual benefit** — EPITA's AI methods and OEL's energy testbeds
10. **Continuation after the visit** — paper, joint supervision, proposal, or recurring exchange
11. **Practical conditions** — workspace, computing, data, funding, IP, insurance, and travel

## Short draft summary for an initial approach

This research visit would develop uncertainty-aware artificial-intelligence methods for energy
decision-making using Open Energy Lab, a reusable environment for scenario generation, physical
simulation, optimization, control, and market evaluation. OEL consolidates two lines developed
earlier in Nicolas's PhD: microgrid management using RL and federated RL, and investment planning
using tractable probabilistic models. The longer-term programme connects three decision horizons:
probabilistic investment planning, operational flexibility through the control of district cooling
and aggregated microgrids, and single- or multi-market participation by battery and aggregated
resources. These problems share uncertainty, physical constraints, and a need for reproducible
comparison, but they are often studied using custom scenarios and evaluation code. OEL supplies a
common experimental backbone so that the scientific contribution can focus on the decision method
and its observed consequences. Its first working market-data implementation is grounded in
accessible French electricity and balancing data, making France both an empirical starting point
for OEL and a natural setting in which to develop the EPITA collaboration.

For a four-to-six-week stay at EPITA, the proposed focal project is distributed control of a
heterogeneous building microgrid through a hybrid MPC–RL architecture. MPC would provide
model-based planning, constraint management, precise activation tracking, and recovery management;
RL would compensate for model mismatch, uncertainty, and coordination or scalability limitations.
The study would compare uncoordinated control, transparent aggregation heuristics, centralized or
distributed MPC, pure RL where appropriate, and selected hybrid couplings under identical weather,
load, asset, and communication scenarios. The aim is to determine whether hybrid control can
stabilize heterogeneous building flexibility into a sufficiently predictable service for one
ancillary-service product. Evaluation would cover cost, comfort, aggregate tracking, rebound,
constraint violations, response time, sustained delivery, availability, scalability, and
generalization to different building mixtures. The aggregation would expose a conservative,
state-dependent service envelope rather than pretending that buildings behave exactly like a
battery. This connects the work to OEL's existing BESS market-participation research through common
commitment, activation, delivery, and settlement concepts. The collaboration would combine EPITA
expertise in machine learning, stochastic methods, optimization, and control with the energy-system
models and reproducible evaluation environment developed through OEL. Expected outputs are a
reproducible benchmark experiment, a reusable OEL distributed-control component, a joint manuscript
or technical-report outline, and a roadmap for continued collaboration.

## Decisions to settle before sending the plan

- Exact dates and whether the visit is four, five, or six weeks.
- The scientific sponsor at EPITA and any additional collaborators.
- The precise hybrid MPC–RL decomposition: aggregator action, local response, observations,
  communication interval, and training objective.
- Which building types, flexible assets, and degrees of heterogeneity form the first benchmark.
- Whether ancillary-service participation is part of the visit's core evidence or a post-visit
  extension after the distributed controller is established.
- What data and plant parameters may be used, shared, or only represented synthetically.
- Funding source and what EPITA is expected to provide.
- The exact administrative meaning and required form of the *convention d'accueil*, including
  affiliation/status, insurance, IP, confidentiality, computing access, and publication terms.
- Whether the formal submission should be in French or English and its required length.

The administrative requirements above should be confirmed directly with EPITA. No public page was
found that establishes a specific visiting-researcher convention process, so the research note
should not infer those terms.
