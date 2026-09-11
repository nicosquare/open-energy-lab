# Guide for an EPITA hosting proposal: distributed AI for energy communities with OEL

**Discussion date:** 2026-09-01
**Status:** Working guide for writing a two-to-four-page research proposal
**Proposed host institution:** EPITA Research Laboratory (LRE), Paris
**Proposed inviter and scientific host:** Éric Moulines, through a *convention d'accueil à EPITA*
**Indicative visit:** Around December 2026; exact dates and duration to be confirmed

## 1. Recommended proposal framing

The proposal should lead with one scientific collaboration rather than with the complete Open
Energy Lab (OEL) roadmap:

> **Can distributed hybrid MPC–RL control make a heterogeneous collective self-consumption
> community sufficiently predictable and reliable to provide energy flexibility and, eventually,
> ancillary services?**

OEL is the enabling experimental backbone. The broader research programme—probabilistic investment
planning, flexible energy control, and market participation—explains why the collaboration matters
beyond one visit, but it should not compete with the focal question.

Suggested English title:

> **Distributed hybrid MPC–RL control of heterogeneous self-consumption communities for reliable
> energy flexibility**

Suggested French title:

> **Commande distribuée hybride MPC–RL de communautés d'autoconsommation hétérogènes pour une
> flexibilité énergétique fiable**

The simplest proposal narrative is:

1. Nicolas has developed two prior AI-for-energy research lines: distributed microgrid management
   using RL and federated RL, and probabilistic investment planning.
2. He is building OEL to consolidate these lines into reusable research infrastructure rather than
   repeatedly creating study-specific simulators and datasets.
3. Discussions with Éric have identified distributed hybrid MPC–RL control as a promising joint
   methodological problem.
4. Éric may facilitate conversations with people involved in collective self-consumption
   communities, giving the visit a concrete French application and stakeholder context.
5. The visit will formulate and prototype one community-control experiment, characterize its firm
   flexibility, and establish a credible path toward ancillary-service participation.

## 2. Research trajectory and the role of OEL

### Prior and ongoing work

The proposal should briefly establish continuity with work that predates the unified library:

- **Microgrid management with RL and federated RL.** This introduced the problems of heterogeneous
  buildings, distributed learning, local information, coordination, and privacy-aware control.
- **Investment planning with tractable probabilistic models.** The manuscript
  [*Tractable Probabilistic Models for Investment
  Planning*](https://arxiv.org/abs/2511.13888), currently under review at *IEEE Transactions on
  Power Systems*, uses sum-product networks to represent high-dimensional uncertainty and embed
  probabilistic reliability requirements in mixed-integer investment planning.
- **Context-sensitive energy scenario generation.** [*WattCouncil: Context-Aware Household Energy
  Scenario Generation With Governed LLMs*](https://doi.org/10.1145/3744256.3812595), published at
  ACM BuildSys 2026, addresses limited household-energy data through governed generation and
  validation of contextual demand scenarios. It is relevant as adjacent work, not as the central
  method proposed for EPITA.

These works provide two main methodological foundations—distributed learning and control, and
probabilistic decision-making under uncertainty—plus experience with the energy-data accessibility
problem.

### Why OEL is being built

OEL is an intentional consolidation of this research trajectory. Its purpose is to provide common,
tested building blocks for:

- real and synthetic weather, demand, and market scenarios;
- physical simulation of energy assets and services;
- optimization, MPC, RL, and other replaceable decision methods;
- planning, commitment, activation, and settlement across decision horizons; and
- reproducible comparison through explicit provenance and evidence.

The justification is not merely that earlier code was unavailable. AI-for-energy studies often
construct bespoke scenarios, physical assumptions, and evaluation scripts, which makes results
difficult to compare. OEL separates the method that produces a decision from the environment that
evaluates its physical and economic consequences.

The wider near-term programme has three application lines:

| Research line | Scientific objective | OEL capabilities to consolidate |
| --- | --- | --- |
| Heterogeneous microgrids and communities | Use distributed hybrid MPC–RL to coordinate local objectives and stabilize aggregate flexibility for grid services | Community composition, local and aggregate control, flexibility envelopes, activation tracking, and market handoff |
| BESS participation in ancillary services | Compare single-market, sequential, and multi-market strategies using common data, physics, and settlement | Market artifacts, commitment interfaces, BESS replay, degradation, settlement, and rolling backtests |
| District-cooling demand flexibility | Use thermal storage and predictive control to improve cost and expose reliable demand flexibility in Gulf conditions | Cooling-load scenarios, plant and storage models, tariffs, threshold/MPC/learned control, and resilience evaluation |

Investment planning remains part of the long-term programme, but its present TPM contribution is
already under review. It should appear as prior and ongoing work, not as a promised duplicate paper.

## 3. Focal collaboration: collective self-consumption communities

### Why this is a useful application context

In France, *autoconsommation collective* refers to local sharing of electricity among multiple
consumers and producers associated through a common legal entity. Participants remain connected to
the distribution grid: the network supplies deficits and carries locally produced energy or
surplus. Enedis describes such operations at the scale of buildings, neighborhoods, municipalities,
or activity zones ([overview](https://www.enedis.fr/tout-savoir-sur-lautoconsommation-collective)).

The proposal should avoid treating the following terms as automatically interchangeable:

- a **microgrid** is the technical abstraction used to model connected local assets and control;
- a **collective self-consumption operation** is a particular organizational and regulatory form
  for sharing local electricity; and
- an **aggregator** is the actor that may coordinate flexibility and interface with an external
  market or system operator.

French renewable-energy communities may access relevant energy markets directly or through an
aggregator, but the applicable legal and contractual route depends on the actual organization
([French Ministry overview](https://www.ecologie.gouv.fr/politiques-publiques/loi-energie-climat)).
For the proposal, the simulated system can be called a **collective self-consumption community**;
its precise legal form and route to market should be validated with Éric's contacts rather than
assumed.

### Proposed system

The initial community would contain a deliberately heterogeneous set of participants:

- residential, commercial, or public buildings with different demand and thermal dynamics;
- local photovoltaic generation;
- individual or shared BESS capacity;
- flexible HVAC, cooling, water heating, EV charging, or other controllable loads;
- participants with different forecasts, comfort constraints, objectives, and available data; and
- a community coordinator and a distinct market-facing aggregator role, even if one organization
  ultimately performs both.

The community has two coupled objectives:

1. **Internal value:** increase local use of renewable production, reduce energy cost and peaks,
   respect participant constraints, and address how benefits or burdens are distributed.
2. **External value:** expose a conservative and dependable flexibility service to the grid or an
   ancillary-service market.

The tension between these objectives is important. Reserving flexibility for an external service
may reduce immediate self-consumption or constrain a participant, while poor internal coordination
may cause the community to overstate what it can deliver.

### Research question and hypothesis

Central question:

> How should MPC and RL be combined across local and aggregate control layers so that a
> heterogeneous self-consumption community meets local objectives while delivering a predictable
> external flexibility service?

Working hypothesis:

> A distributed hybrid controller can stabilize the time-varying, state-dependent response of
> heterogeneous buildings into a more reliable flexibility resource: MPC supplies constrained
> predictive precision, while RL adapts to model mismatch, uncertainty, and coordination
> complexity.

Supporting questions:

1. What information must participants share, and what can remain local?
2. Which quantities should MPC calculate, and which model errors, residual actions, coordination
   signals, parameters, or value functions should RL learn?
3. Can the controller generalize to different numbers and mixtures of buildings?
4. How should internal self-consumption objectives be traded against reserve availability and
   external revenue?
5. How can a state-dependent response be converted into a firm upward/downward flexibility offer
   with an explicit confidence level and recovery requirement?
6. How do forecast errors, communication failures, unavailable participants, and distribution
   shift affect delivery reliability?

### Candidate control architecture

```text
French grid and ancillary-service context
                    |
                    v
       market-facing aggregator interface
        commitment, activation, settlement
                    |
                    v
      hybrid MPC–RL community coordinator
   allocation, prediction, adaptation, tracking
          |             |             |
          v             v             v
   local controller  local controller  shared assets
     building A        building B      PV / BESS
          |             |             |
          +-------------+-------------+
                    |
                    v
      community energy sharing and delivery
                    |
                    v
       OEL physical replay and evidence
```

The proposal should not reduce MPC to comfort enforcement or assume that RL must be the
aggregator. MPC can provide trajectory planning, explicit dynamics, hard constraints, accurate
activation tracking, reserve margins, and recovery/rebound management. RL is useful because pure
model-based control can suffer from model mismatch, forecast error, and scaling or communication
costs; pure RL can be sample-inefficient, imprecise, or unreliable outside its training
distribution.

Three coupling patterns are worth considering, with one selected after the first joint design
sessions:

1. **MPC-led:** MPC computes constrained decisions and RL learns bounded residuals, model-error
   corrections, parameters, or terminal values.
2. **RL-led:** RL proposes allocations or references and MPC corrects them before execution.
3. **Hierarchical:** RL coordinates slower community-level allocation while distributed MPC handles
   fast local planning and tracking.

An MPC-led hybrid is a sensible initial hypothesis when precision and market reliability motivate
the combination, but the architecture should remain an experimental choice rather than a conclusion.

### From variable flexibility to a reliable service

The aggregation is interesting precisely because it does not behave naturally like one large
battery. Its available power and energy are asymmetric, time-varying, uncertain, participant-
dependent, and affected by comfort and rebound. The research objective is to control and
characterize those properties well enough to expose a conservative service contract containing:

- upward and downward capacity;
- response time and ramp behavior;
- sustainable activation duration;
- availability and confidence;
- baseline and tracking accuracy;
- post-activation recovery and rebound; and
- expected non-delivery risk or reserve margin.

The study should first prove aggregate tracking under physical constraints, then construct the
firm flexibility envelope, and only then test one selected ancillary-service product. Full
multi-market optimization is a later extension, not a prerequisite for the EPITA visit.

### Experimental comparison

Candidate baselines are:

- self-consumption-only or uncoordinated local control;
- a transparent rule- or price-based community coordinator;
- centralized MPC as a small-community reference, where tractable;
- distributed or hierarchical MPC;
- pure RL, where meaningful; and
- one or more hybrid MPC–RL couplings.

The experiment should evaluate three groups of metrics:

| Perspective | Metrics |
| --- | --- |
| Community | Self-consumption and self-sufficiency, cost, peak demand, participant service or comfort, fairness or allocation effects |
| Grid/market | Available capacity, response time, tracking error, sustained duration, recovery, rebound, availability, qualification-compatible pass rate, revenue, and non-delivery penalties |
| Method | Constraint violations, computation time, communication, sample efficiency, scalability, and generalization to unseen community compositions |

Simulation can show that a controller meets modeled requirements for a selected product. It cannot
by itself claim formal market qualification, which may also require certified hardware, telemetry,
tests, contracts, and approval by the relevant parties.

## 4. Role of prospective community contacts

Éric's offer to introduce people working around self-consumption communities can make the project
substantially stronger. Their role should initially be described as **prospective domain
interlocutors**, not confirmed project partners or data providers.

The conversations could validate:

- typical community composition and ownership models;
- local generation, storage, and controllable-load configurations;
- actual operating objectives and allocation rules;
- available measurements, temporal resolution, and privacy constraints;
- current control practices and sources of forecast or model error;
- practical causes of unavailable flexibility and rebound;
- interest in grid services and the perceived technical or contractual barriers; and
- whether anonymized data, parameters, or a representative synthetic case could be shared.

Expected output from these discussions should be modest but concrete: a reviewed requirements
note, a defensible reference topology, documented model assumptions, and possibly a pathway to a
future applied case study. The proposal should not depend on receiving private operational data
during a short visit. OEL must support a well-grounded synthetic benchmark if access is delayed or
restricted.

## 5. What OEL already provides and what the visit would add

| Area | Available foundation | Development needed for the focal project |
| --- | --- | --- |
| Scenarios | Versioned weather and weather-conditioned demand artifacts; synthetic and real-data provenance | Community composition, participant diversity, occupancy or routine scenarios, and train/test population splits |
| Physical systems | Battery and service replay; reusable simulator components | Grid-connected community balance, heterogeneous building assets, shared generation/storage, and recovery dynamics |
| Control | Deterministic controllers, robust FCR bidding, and rolling-study orchestration | Local MPC boundary, hybrid MPC–RL interface, community coordinator, and communication contract |
| Markets | French day-ahead/FCR context; direct RTE aFRR/mFRR artifacts; information cutoffs and settlement components | One community flexibility contract and one product-compatible commitment/activation adapter |
| Planning and uncertainty | TPM artifacts, conditional queries, and optimization embedding | Optional longer-term link; not required for the visit prototype |
| Evidence | Immutable artifacts, fingerprints, explicit derived-simulation labels, and offline reproducibility | Community-, controller-, and qualification-evidence records |

### France as the initial implementation context

OEL is country-extensible, but its first working market-facing version has a concrete French
foundation. France's public electricity-data ecosystem made it possible to start with real market
and balancing observations rather than wholly synthetic traces. RTE's [public API
portfolio](https://www.services-rte.com/files/live/sites/services-rte/files/API%20acteurs%20de%20march%C3%A9%20RE-AA-RR-GRD%20Version%20publique%202024-02-27.pdf)
includes production, consumption, balancing, capacity-mechanism, and cross-border information,
although individual APIs can still require registration and credentials.

OEL currently implements the RTE Balancing Energy API v5.2 for French aFRR and mFRR observations,
alongside French-context day-ahead, FCR, BESS replay, settlement, and rolling-study workflows. The
design principle is:

> **France-specific first, source-independent by design.**

RTE- and ENTSO-E-specific acquisition remains at the library boundary. Canonical artifacts allow
controllers and evaluators to remain independent of a particular response format, while product,
settlement, and qualification rules remain explicit rather than falsely universal.

Public RTE aFRR/mFRR values are control-area observations, not high-frequency commands sent to an
individual resource. OEL can use them as market context or in a clearly labeled derived simulation;
they do not prove historical dispatch, settlement, or qualification. Open availability also does
not imply unrestricted redistribution, so credentials, attribution, licensing, and retention must
remain explicit.

### Optional role for WattCouncil

WattCouncil could be an optional upstream producer for diverse household routines, contextual base
loads, or participant mixtures:

```text
WattCouncil scenario generation
            |
            v
OEL validation and provenance adapter
            |
            v
synthetic community demand artifacts
```

It would enrich the scenario distribution but would not define controllable building dynamics,
comfort states, HVAC flexibility, response speed, or rebound. Those remain responsibilities of the
OEL physical and control models. This keeps LLM research outside the core EPITA contribution.

## 6. Why EPITA and why this visit

The EPITA fit is methodological and relational:

- Éric Moulines is an EPITA AI professor in Paris and is also at MBZUAI. His expertise includes
  probabilistic machine learning, uncertainty quantification, stochastic optimization, time-series
  methods, and control of complex systems ([EPITA](https://www.lre.epita.fr/members/eric-moulines/),
  [MBZUAI](https://mbzuai.ac.ae/study/faculty/professor-eric-moulines/)).
- The scientific question emerged from direct discussions with Éric rather than from searching for
  an institutional label after defining the project.
- His potential introductions to self-consumption-community practitioners provide a route to
  validate the system model and practical questions.
- EPITA's AI research and computation environment can contribute learning, optimization, and
  reproducible experimentation; OEL contributes energy-system models, French data contracts, and
  the evaluation environment.

Marc Plantevit may be a secondary contact for the longer-term market line because of his work on
electricity-price forecasting and differentiable market optimization, even though he is based in
Lyon ([profile](https://www.lre.epita.fr/members/marc-plantevit/)). Institutional arrangements can
be discussed with EPITA research leadership after the scientific host and visit scope are agreed.

The mutual benefit should be stated plainly:

- **For EPITA:** a concrete constrained-control and distributed-AI problem, an energy testbed, and
  a path to applied contacts and publications.
- **For Nicolas and MBZUAI:** methodological collaboration, validation in a French community and
  market context, and a reusable OEL research component.
- **For external community contacts:** a transparent way to test control and flexibility ideas
  without exposing operations to an unvalidated controller.

## 7. Proposed four-to-six-week visit plan

Substantial OEL preparation should occur before arrival so that the visit is used for joint
research rather than basic software setup.

| Period | Main activity | Evidence or output |
| --- | --- | --- |
| Before arrival | Progress the candidate MPC–RL couplings and prepare reusable OEL building blocks, a small synthetic heterogeneous case, and baseline controllers | Two-page method note, reproducible environment, initial scenario bundle |
| Week 1 | Work with Éric and, if available, prospective community contacts to shape the final topology, objectives, data boundary, and MPC–RL coupling | Reviewed requirements and experiment contract |
| Week 2 | Implement community interfaces and pure/rule/MPC baselines; freeze metrics, scenarios, seeds, and information boundaries | Reproducible baseline experiment |
| Weeks 3–4 | Implement and train the selected hybrid controller; evaluate tracking, constraints, communication, and generalization | Core technical results and failure analysis |
| Week 5 | Estimate a firm flexibility envelope; evaluate a selected French frequency-regulation case and its interaction with energy arbitrage | Qualification-oriented simulation and economic evidence |
| Week 6 | Run sensitivities, write the paper structure, present results, and agree post-visit work | Draft manuscript or report outline, seminar, and collaboration roadmap |

If the visit is only four weeks, the core deliverable ends after the hybrid-control comparison.
The market connection can be specified and implemented after the visit rather than rushed.

## 8. Expected outputs

A credible proposal should promise:

1. a jointly defined research question and evaluation protocol;
2. a stakeholder-informed self-consumption-community reference model;
3. one reusable OEL community/control interface;
4. a reproducible comparison of MPC, RL, and hybrid control;
5. preliminary flexibility-reliability evidence and, if feasible, one bounded
   frequency-regulation demonstration alongside an arbitrage comparison;
6. an EPITA seminar or research presentation; and
7. a joint manuscript, technical report, student-project, or funding roadmap.

It should not promise three completed papers or a commercially qualified aggregator within several
weeks.

## 9. Template for the formal proposal

For a two-to-four-page document, use the following order:

| Section | Purpose | Approximate space |
| --- | --- | --- |
| Title and visit information | Applicant, EPITA host, place, dates, and duration | Header |
| Context and trajectory | Prior microgrid/RL and TPM work; why OEL was created | 0.5 page |
| Problem and objective | Self-consumption communities, heterogeneity, and reliable flexibility | 0.5 page |
| Research questions and method | Hybrid MPC–RL architecture, baselines, scenarios, and evidence | 1 page |
| French and EPITA relevance | Open French data, Éric's methodological fit, and prospective community contacts | 0.5 page |
| Work plan and outputs | Pre-visit preparation, weekly milestones, and realistic deliverables | 0.5 page |
| Continuation and practical conditions | Paper/funding path, data, IP, computing, and administration | 0.5 page |

The proposal should spend most of its space on the focal project. The wider OEL programme and venue
portfolio belong in one short context paragraph or an appendix.

### Draft executive summary

Open Energy Lab is being developed as a reusable environment for AI-based energy research,
consolidating prior work on microgrid management with reinforcement and federated learning and on
probabilistic investment planning. Its first market-facing implementation is grounded in accessible
French electricity and balancing data while retaining source-independent simulation, control, and
evaluation contracts.

The proposed visit to EPITA will investigate distributed hybrid model predictive control and
reinforcement learning for a heterogeneous collective self-consumption community. Local buildings,
generation, storage, and flexible loads must coordinate local renewable-energy use and participant
constraints while producing an aggregate response that may be offered to the grid through an
aggregator. MPC will provide constrained predictive planning and accurate tracking; RL will address
model mismatch, uncertainty, and coordination complexity. The study will compare rule-based,
model-based, learning-based, and hybrid approaches under common OEL scenarios and evaluate local
self-consumption, cost, service constraints, aggregate tracking, response time, duration, recovery,
scalability, and generalization.

Discussions with Éric Moulines and, if available, contacts involved in self-consumption communities
will inform the reference topology, practical assumptions, and data boundary. The experiments will
remain synthetic-first, using documented and physically reasonable assumptions while preserving
the option to consume suitable APIs or real data through OEL adapters. The initial goal is to
characterize a conservative, state-dependent flexibility envelope and test it against one French
frequency-regulation use case, with arbitrage treated as a complementary economic objective—not to
claim commercial qualification. Expected outputs are a reviewed experimental protocol, a reusable
OEL community-control component, reproducible preliminary results, and a joint publication or
follow-up-project roadmap.

## 10. Publication landscape and deadlines

This table is an internal planning aid, not a promise to target every venue. Deadlines were checked
on **1 September 2026** and must be verified again before submission. Regular journal submissions
are rolling; an unannounced conference deadline is marked TBA.

| Venue | Best candidate contribution | Next submission deadline or status |
| --- | --- | --- |
| [*IEEE Transactions on Power Systems*](https://ieee-pes.org/publications/transactions-on-power-systems/) | Grid-oriented hybrid control, flexibility reliability, or BESS markets | Rolling |
| [PSCC 2028](https://pscc2028.nl/) | Distributed power-system control, markets, or uncertainty | Paper deadline TBA; conference 26–30 June 2028 |
| [*Applied Energy*](https://www.sciencedirect.com/journal/applied-energy) | Applied storage, community flexibility, or district-energy optimization | Rolling |
| [*Energy and Buildings*](https://www.sciencedirect.com/journal/energy-and-buildings) | District cooling or building/community flexibility | Rolling |
| [*Building and Environment*](https://www.sciencedirect.com/journal/building-and-environment) | Building performance, HVAC, thermal conditions, or controls | Rolling |
| [ACM e-Energy 2027](https://energy.acm.org/conferences/eenergy/2027/pages/cfp.php) | OEL/BESS market evaluation or computing-oriented community control | Fall registration 11 September 2026 and paper 18 September 2026, AoE; winter dates TBA |
| [ACM BuildSys 2027](https://buildsys.acm.org/2027/) | Distributed computing and control for self-consumption communities | Paper deadline TBA; event announced for 5–11 June 2027 |
| [IBPSA Building Simulation 2027](https://bs2027.org/) | District-cooling thermal-storage study | Abstract 1 September 2026, 23:59:59 CEST; full paper 15 January 2027 after abstract acceptance |
| [*Journal of Building Performance Simulation*](https://www.tandfonline.com/journals/tbps20/about-this-journal) | OEL simulation method, community control, or district cooling | Rolling; [Control Technologies for Buildings special issue](https://think.taylorandfrancis.com/special_issues/innovation-implementation-control-technologies-buildings/) due 31 May 2027 |

Each contribution must own a distinct result:

- the community paper: hybrid distributed control and dependable flexibility;
- the BESS paper: fair single-/multi-market comparison and empirical findings;
- the district-cooling paper: thermal-storage operation and flexibility findings; and
- a future OEL methods paper: reusable simulation/evaluation methodology demonstrated across more
  than one sufficiently complete study.

## 11. Claims and boundaries

### Defensible claims for the proposal

- OEL actively consolidates a research trajectory rather than retrofitting a library to a paper.
- Its first working market layer is grounded in accessible French and European data interfaces.
- It separates source-specific acquisition, decision production, physical replay, and evaluation.
- The visit will study whether hybrid control can make community flexibility more predictable and
  reliable.
- Practitioner conversations will inform assumptions and relevance even if no private data is
  ultimately shared.

### Claims to avoid until evidence exists

- OEL is the first or only AI-for-energy library.
- A collective self-consumption operation is legally or physically identical to a microgrid,
  energy community, aggregator, or BESS.
- Public control-area data represents commands or settlement for an individual asset.
- Simulation constitutes formal ancillary-service qualification.
- Éric's contacts are committed partners, data providers, or co-authors.
- The present OEL version already implements distributed community control or complete
  multi-market optimization.

## 12. Working decisions and remaining confirmations

The following assumptions can now guide the first English proposal. Items marked **provisional**
should be presented as directions to refine with Éric rather than as fixed design choices.

| Question | Current answer | Status or implication for the proposal |
| --- | --- | --- |
| Visit dates | The visit is expected around **December 2026**. | Provisional; exact dates and duration remain to be confirmed. |
| Host arrangement | Éric would invite Nicolas to EPITA through a *convention d'accueil à EPITA*. | Use Éric as the proposed inviter and scientific host; administrative details still require confirmation. |
| Community contacts | The relevant people and their possible roles are not yet known. | Do not name or imply committed partners. Refer only to possible introductions and optional stakeholder discussions. |
| Initial topology | Reusable community assets and interfaces will be prepared in OEL before the visit; the reference topology will be shaped jointly during the visit. | Pre-visit work should enable discussion rather than prematurely fix the case. |
| Community framing | Model an **autoconsommation collective** operation with the potential to offer flexibility and ancillary services through an appropriate market interface. | Working framing; retain the distinction between the operation, its technical microgrid abstraction, and the aggregator. |
| First MPC–RL coupling | The architecture remains to be selected and will be progressed before the visit. | Provisional; the proposal can present MPC-led, RL-led, and hierarchical alternatives while identifying an MPC-led hybrid as the initial hypothesis. |
| Market use case | Frequency regulation is the likely qualification-oriented application; energy arbitrage is also of interest. | Exact French frequency product remains open. Treat arbitrage as an economic objective, baseline, or later value-stacking component—not as an ancillary service. |
| Data strategy | Use synthetic data generated from documented, physically reasonable assumptions by default, while allowing APIs or real data to be consumed through adapters, as with ENTSO-E and RTE. | The proposal does not depend on private data. Clearly separate synthetic, derived, and directly observed inputs. |
| Proposal language | Prepare the first proposal in English. | Length and institutional template remain to be confirmed. |
| Practical conditions | Funding, workspace, computing, insurance, confidentiality, IP, publication, and data-retention terms are not yet known. | Resolve these after the scientific proposal and visit are provisionally accepted; do not speculate in the first draft. |

The first proposal can therefore be scientifically specific without pretending that the case study,
controller architecture, market product, contacts, or administrative conditions are already fixed.
