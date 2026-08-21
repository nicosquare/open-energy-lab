# Roadmap Note: From TPM Planning to BESS Stacked Services

**Date:** 2026-08-20  
**Updated:** 2026-08-21  
**Status:** Discussion summary and proposed feature direction

## Purpose

This note summarizes the discussion about what Open Energy Lab should develop
after feature `009-tpm-planning`, given the longer-term objective of studying a
battery energy storage system (BESS) participating in both energy arbitrage and
frequency regulation.

The central conclusion is that feature 009 supplies the reusable probabilistic
planning machinery needed for that direction. The next capability should define
and validate the physical and market semantics of stacked BESS services before
adding forecast-aware MPC or learned controllers.

That capability should not be limited to synthetic market fixtures. Feature 010
should introduce an authenticated ENTSO-E Transparency Platform adapter as a
library-owned market-data producer, use a selected historical period for its
real-data demonstration, and preserve a small deterministic scenario for
equation-level validation. Live retrieval and offline reproducibility are
complementary requirements: simulations consume a versioned local market-data
artifact, while an explicit retrieval operation creates or refreshes that
artifact from ENTSO-E.

FCR should remain the deliberately narrow first balancing product. The next
feature should extend the same market-data, dispatch, and settlement boundaries
to automatic Frequency Restoration Reserve (aFRR) and manual Frequency
Restoration Reserve (mFRR). These products should be added as explicit market
profiles rather than treated as interchangeable regulation-signal columns.

## What Feature 009 Now Enables

Feature 009 was intended to reproduce the central concept from
[Tractable Probabilistic Models for Investment Planning](https://arxiv.org/html/2511.13888v3),
not necessarily every numerical experiment in the paper.

The paper's core method has three layers:

1. A simulator evaluates a design under stochastic realizations and labels the
   outcome, conceptually mapping `(design, uncertainty) -> adequacy outcome`.
2. A tractable probabilistic model, specifically an SPN, learns the joint or
   conditional distribution of designs, uncertainties, and outcomes.
3. The learned probabilistic computation is embedded in an MILP so that a
   design can be optimized subject to a chance constraint.

Feature 009 now provides the same conceptual pipeline within the current
library architecture:

- stochastic weather and weather-conditioned demand families;
- battery-and-solar design sweeps using common absolute-indexed uncertainty
  samples;
- simulator-owned adequacy outcomes and persisted planning datasets;
- real current-SPFlow fit, persistence, query, and marginalization;
- current-SPFlow-to-MIO compilation;
- Pyomo/HiGHS chance-constrained design optimization;
- native-SPFlow verification of the selected design; and
- held-out calibration and conservative recommendation gates.

This is sufficient to claim a functional reproduction of the paper's planning
concept. Reproducing the paper's complete data-regime study, hyperparameter
sweeps, scenario baselines, figures, or exact numerical results is not required
for the intended roadmap.

Feature 009 should therefore be treated as a reusable decision-under-uncertainty
engine rather than the end of the planning work.

## Clarification About Oracle Forecasts

A full-horizon look-ahead oracle that receives the realized future and optimizes
the same objective under the exact simulator model is a clairvoyant optimum. A
fair deployable controller cannot be expected to outperform it.

An oracle remains useful for:

- validating optimization equations and implementation;
- defining an upper bound on achievable revenue or a lower bound on cost;
- calculating the regret of deployable controllers; and
- measuring the potential value of improved forecasts.

It must not be used as the principal deployable-controller benchmark. Routine
comparisons should use leakage-free forecasts and give competing controllers
equivalent information. A finite-horizon oracle MPC can also remain suboptimal
relative to a full-episode oracle because it cannot account perfectly for events
beyond its control horizon or for an imperfect terminal-value approximation.

## Target BESS Service-Stacking Architecture

Joint arbitrage and frequency regulation naturally separates into four layers:

| Layer | Responsibility |
| --- | --- |
| Market data | Retrieve, normalize, validate, and persist price and balancing data independently of simulation. |
| Investment planning | Select BESS power, energy capacity, and potentially the operating-policy family. |
| Market scheduling | Allocate power and state-of-charge headroom between the energy market and regulation commitments. |
| Real-time tracking | Follow the regulation activation signal while respecting battery and market constraints. |

Feature 009 substantially supports the investment-planning layer. The market
scheduling and real-time tracking layers are not yet modeled, and there is not
yet a first-class European market-data producer for them.

For a stacked service, realized battery power is conceptually the combination
of an energy-market baseline and a regulation response:

```text
battery power = energy baseline + regulation response
```

The simulator must enforce this combined request against charge/discharge power,
SOC, efficiency, grid, and service-delivery constraints. Regulation headroom is
therefore coupled to arbitrage: power or energy committed to one service may no
longer be available to the other.

The term "frequency regulation" also needs an explicit scope decision. An ISO
or system-operator ancillary-service product driven by an AGC/regulation signal
has different control, settlement, and performance semantics from autonomous
frequency-deviation or droop response. A market-neutral base contract can
support either direction, but the first concrete reference scenario should
select one.

## ENTSO-E Market-Data Integration Vision

Feature 010 should add a narrow, reusable module such as
`open_energy_lab.market.entsoe`. Its responsibility is to access the
[ENTSO-E Transparency Platform REST API](https://documenter.getpostman.com/view/7009892/2s93JtP3F6),
normalize the returned XML documents, validate their temporal coverage, and
write a canonical market-data artifact. The stacked-service simulator should
depend on that artifact contract, not on ENTSO-E networking or XML response
types.

The first adapter profile should target France and the data needed by the
robust-storage-bidding reference case:

| Required series | ENTSO-E document type | Initial treatment |
| --- | --- | --- |
| Day-ahead energy prices | `A44` price document | Required real-data input. |
| Contracted reserve capacity | `A81` contracted reserves | Retrieve and validate FCR coverage for the selected French period. |
| Contracted reserve prices | `A89` contracted reserve prices | Preferred source for FCR capacity remuneration, with RTE data as an explicit alternative if platform coverage is incomplete. |
| Activated balancing quantities | `A83` activated balancing quantities | Evaluate as supporting validation data; do not assume it is the required 10-second normalized FCR signal. |
| Activated balancing prices | `A84` activated balancing prices | Optional when the chosen settlement profile pays activation energy. |

The France bidding-zone/control-area EIC is `10YFR-RTE------C`. Every request
must record the area, requested period, document and business/process filters,
retrieval time, parser/schema version, and source endpoint. The raw response or
an integrity digest should be retained according to the source's redistribution
terms. API acknowledgements, empty results, duplicate intervals, missing
intervals, unexpected resolutions, and daylight-saving transitions must be
reported explicitly rather than silently filled.

### Authentication And Secret Handling

The caller supplies a valid ENTSO-E API token to the retrieval boundary. A
library call may accept it explicitly, while a command-line workflow should
normally read a dedicated environment variable such as `ENTSOE_API_TOKEN`.
The token must never be written into artifacts, cache keys, logs, notebooks, or
test recordings. Authentication is needed only while fetching or refreshing
data; it is not needed to replay an already created artifact.

### Period Retrieval, Not Mandatory Per-Run Fetching

The normal contract is period-based. A user selects a start and end instant,
for example one French market day, one month, or a backtest interval. The
adapter queries that interval and divides it into supported request windows
when necessary. Internally, all instants should be normalized to UTC, while
the original market timezone and delivery-period meaning remain in metadata.
The interval boundary convention should be explicit, preferably start-inclusive
and end-exclusive.

This is not a streaming, real-time control feed. ENTSO-E publishes market and
balancing documents that can be polled, but a simulation should not make an
uncontrolled network request on every execution. Three explicit access modes
are preferable:

| Mode | Behavior | Intended use |
| --- | --- | --- |
| `offline` | Read an existing canonical artifact and never use the network. | Tests, reproducible studies, and repeated simulation. |
| `fetch` | Retrieve a requested period and create a new artifact. | Initial dataset acquisition. |
| `refresh` | Re-query a requested period and create a new version if source data changed. | Publication updates and scheduled ingestion. |

A future near-real-time experiment could schedule repeated `refresh` calls for
the most recent available interval, but it would still be polling a publication
API rather than receiving the physical FCR control signal. Battery tracking at
10-second resolution must replay a separately sourced activation or frequency
trace unless ENTSO-E coverage is proven to satisfy that contract.

### Canonical Artifact Boundary

The data flow should be:

```text
ENTSO-E API / explicit RTE fallback / activation-trace source
                           |
                           v
              market-data producer module
          authenticate -> fetch -> parse -> validate
                           |
                           v
              versioned MarketDataArtifact
          values + units + intervals + provenance
                           |
              +------------+-------------+
              v                          v
    stacked-service simulator     bidding optimizer
```

This boundary makes a single retrieved period reusable across simulator,
optimization, TPM-dataset generation, notebooks, and regression tests. It also
allows later sources to implement the same artifact contract without adding
source-specific logic to battery or market-settlement code.

### First Demonstration And Offline Validation

The feature should include both:

1. a very small deterministic scenario whose expected SOC and revenue can be
   verified by hand; and
2. a selected historical French day retrieved through the ENTSO-E module,
   normalized into a versioned artifact, and replayed end to end.

The second item is real data even when its normalized artifact is subsequently
used as an offline test fixture. Here, "fixture" describes repeatable storage
and validation, not synthetic origin. Routine CI should use the recorded,
provenanced artifact; an optional credentialed integration check should fetch a
small period and compare its schema and invariants without making network
availability a condition of every simulation or test run.

## Expansion Beyond FCR: aFRR And mFRR

After the FCR reference profile is validated, the library should add aFRR and
mFRR as the next market profiles. ENTSO-E identifies
[PICASSO](https://www.entsoe.eu/network_codes/eb/picasso/) as the European
platform for balancing energy from reserves with automatic activation and
[MARI](https://www.entsoe.eu/network_codes/eb/mari/) as the corresponding initiative
for reserves with manual activation.

They should not be folded into Feature 010 because their operational contracts
are materially different:

| Product | Primary response | Simulator implication |
| --- | --- | --- |
| FCR | Continuous containment response to frequency deviation | Symmetric capacity commitment, headroom, and high-resolution normalized response. |
| aFRR | Automatically dispatched restoration response | Directional bids, automatic activation trajectory, activation-energy settlement, and tracking-performance semantics. |
| mFRR | Manually requested scheduled or direct restoration response | Discrete activation events, requested start/duration, ramp and delivery validation, and event-based settlement. |

Feature 011 should reuse the ENTSO-E producer and canonical artifact boundary,
adding only the product-specific capacity, bid, price, activation, and
settlement fields required by aFRR and mFRR. The Transparency Platform's
balancing documents can provide contracted reserves and prices, accepted
offers, activated quantities, and activated prices, but coverage and resolution
must be verified for the selected area and period. The implementation must not
infer an activation signal from a price or aggregated energy series.

The first aFRR/mFRR release should remain simulation-focused: ingest historical
market periods, accept fixed valid commitments and activation inputs, replay
battery response, and calculate product-specific delivery and settlement.
Joint bidding optimization across FCR, aFRR, and mFRR should follow only after
all three market profiles have independent deterministic and real-data
validation.

## Alignment With The Robust Storage Bidding Baseline

The intended reference case is
[lauinger/robust-storage-bidding](https://github.com/lauinger/robust-storage-bidding),
which supplements
[Storage Participation in Electricity Markets: Time Discretization through Robust Optimization](https://arxiv.org/abs/2510.10856).
It studies a storage operator jointly bidding into a day-ahead energy market
and a symmetric Frequency Containment Reserve (FCR) product. Its distinguishing
feature is not a forecast of the realized regulation signal. Instead, it
chooses bids that remain physically deliverable for every activation signal in
a market-inspired uncertainty set.

This gives the first Open Energy Lab regulation feature a concrete scope:

- European-style day-ahead arbitrage plus symmetric FCR capacity;
- an optional intraday energy adjustment in a later user story;
- robust commitment feasibility before realized-signal backtesting; and
- one high-resolution FCR activation trace used to validate the selected bids.

The external repository remains reference evidence rather than a runtime
dependency. Reusable behavior should be implemented natively under
`src/open_energy_lab`, with exact source URLs and version provenance recorded
in fixtures and migration notes.

### Reference Variables And Library Mapping

The reference formulation uses the following market decisions:

| Reference symbol | Meaning | Proposed library concept |
| --- | --- | --- |
| $x^0_t$ | Day-ahead energy power baseline | `EnergyBaselineSchedule` |
| $x^r_b$ | Symmetric FCR capacity bid for block $b$ | `FCRCapacitySchedule` |
| $x^a_t$ | Intraday energy adjustment | `IntradayAdjustmentSchedule` |
| $\xi_s$ | High-resolution normalized FCR activation | `RegulationActivationTrace` |
| $\gamma,\Gamma$ | Activation-duration budget and recovery cycle | `ActivationBudgetUncertaintySet` |
| $y_s$ | Battery state of charge | Simulator-owned battery state |

The reference code defines positive power as battery discharge. At regulation
substep $s$, belonging to energy interval $t(s)$ and FCR block $b(s)$, its
requested physical power is

$$
p^{\mathrm{ref}}_s
= x^0_{t(s)} + x^a_{t(s)} + \xi_s x^r_{b(s)}.
$$

Open Energy Lab currently defines positive battery dispatch as charge. The
adapter must therefore convert signs explicitly:

$$
p^{\mathrm{OEL}}_s = -p^{\mathrm{ref}}_s.
$$

The library-wide sign convention should not be changed to imitate the external
reference.

### Multi-Rate Time Contract

The reference experiments use four relevant resolutions:

| Quantity | Reference resolution |
| --- | --- |
| Day-ahead energy bid $x^0$ | 1 hour |
| Robust optimization state grid | 15 minutes |
| FCR capacity bid $x^r$ | Constant for 4 hours |
| Realized activation signal $\xi$ | 10 seconds |

For a 24-hour day this corresponds to 24 energy bids, 96 robust state periods,
6 FCR blocks, and 8,640 regulation samples. These values should be configurable,
but the first reference fixture should use them to exercise multi-rate
alignment explicitly.

### Battery Dynamics

Using the reference positive-discharge convention, define

$$
p_s^+ = \max(p_s,0),
\qquad
p_s^- = \max(-p_s,0).
$$

For regulation timestep $\delta t$, charging efficiency $\eta_c$, and
discharging efficiency $\eta_d$, exact signal replay updates SOC as

$$
y_{s+1}
= y_s
+ \delta t\left(\eta_c p_s^- - \frac{p_s^+}{\eta_d}\right).
$$

The detailed simulator must enforce

$$
\underline{x} \le p_s \le \overline{x},
\qquad
\underline{y} \le y_s \le \overline{y}
$$

at every high-resolution substep. It must report requested power separately
from physically delivered power whenever a deliberately invalid test schedule
would require clamping.

### Robust Power Headroom

The regulation signal is normalized so that $-1\le\xi_s\le1$. Robust power
feasibility for the combined bid requires

$$
\underline{x}
\le
x^0_t+x^a_t+\xi x^r_b
\le
\overline{x},
\qquad \forall \xi\in[-1,1].
$$

For symmetric reserve $x^r_b\ge0$, the pointwise power envelope becomes

$$
x^0_t+x^a_t-x^r_b \ge \underline{x},
$$

$$
x^0_t+x^a_t+x^r_b \le \overline{x}.
$$

These constraints express the immediate charge and discharge headroom cost of
committing capacity to FCR.

### Activation Uncertainty Set

Pointwise power headroom is not sufficient because a sustained activation can
also exhaust the battery's energy headroom. The baseline uses a
market-inspired activation budget with maximum normalized activation duration
$\gamma$ over a recovery cycle $\Gamma$. A useful abstract representation is

$$
\mathcal U_{\gamma,\Gamma}
=
\left\{
\xi:
|\xi(t)|\le1,
\quad
\int_{a}^{a+\Gamma}|\xi(t)|\,dt\le\gamma
\quad\text{for every admissible window }a
\right\}.
$$

The reference defaults are $\gamma=0.25$ hours and
$\Gamma=2+\gamma=2.25$ hours. The exact window/budget semantics implemented in
Open Energy Lab must be fixed by tests against the cited reference functions;
the equation above records the intended contract rather than authorizing a
looser interpretation.

Robust SOC feasibility is then

$$
\underline{y}
\le
y_k(x^0,x^a,x^r,\xi)
\le
\overline{y},
\qquad
\forall \xi\in\mathcal U_{\gamma,\Gamma},
\quad \forall k.
$$

The crucial implementation goal is to replace this infinite family of signal
constraints with the finite deterministic robust counterpart validated by the
reference formulation. Detailed signal replay remains a post-solve validation
layer and does not substitute for the robust constraints.

### Market Objective And Settlement

Let $\pi^0_t$ be the day-ahead energy price, $\pi^r_b$ the FCR capacity price,
and $c^{\mathrm{slack}}$ the penalty on SOC or terminal violations. A simplified
version of the bidding objective is

$$
\max_{x^0,x^a,x^r}
\left[
\sum_t \Delta t\,\pi^0_t(x^0_t+x^a_t)
+ \sum_b \pi^r_b x^r_b
- c^{\mathrm{slack}}S
\right],
$$

where $S$ collects explicitly modeled feasibility slack. Intraday prices can
be separated from day-ahead prices when the intraday user story is enabled.

For a market that pays regulation energy, realized high-resolution settlement
can instead use

$$
\Pi^{\mathrm{real}}
=
\sum_s \delta t\,\pi^0_{t(s)}p_s
+ \sum_b \pi^r_b x^r_b.
$$

The simulator must preserve a decomposition into day-ahead, FCR, intraday, and
total realized profit. A degradation proxy may be added later as

$$
C^{\mathrm{deg}}
= c^{\mathrm{throughput}}
\sum_s \delta t\,|p_s|,
$$

but it should be disabled in the initial reference-parity case because it is
not part of the baseline objective.

### Exact, Restricted, And Relaxed Problems

The reference develops an exact mixed-integer bilinear formulation together
with mixed-integer linear restrictions and relaxations. For a maximization
problem, their optimal objectives should satisfy

$$
z_{\mathrm{restriction}}
\le
z_{\mathrm{exact}}
\le
z_{\mathrm{relaxation}}.
$$

This matches the repository's backend policy well:

- the MILP restriction should be the required, operationally feasible HiGHS
  path;
- the MILP relaxation should provide an upper bound and an observable
  optimality-gap estimate; and
- the exact nonconvex bilinear formulation should be an optional Gurobi parity
  check for small cases.

The external Julia/JuMP/Gurobi implementation must not become a runtime
dependency or a routine validation requirement.

### Reference Parameter Profile

The first committed reference-style scenario should use the baseline's bounded
case rather than its full four-year backtest:

| Parameter | Reference-style value |
| --- | --- |
| Charge/discharge power | $\pm50$ kW in reference sign convention |
| SOC bounds | 10--90 kWh |
| Charge/discharge efficiency | 0.92 / 0.92 |
| Horizon | 24 hours |
| Robust timestep | 0.25 hours |
| Regulation replay timestep | $1/360$ hour (10 seconds) |
| FCR bid duration | 4 hours |
| Activation budget $\gamma$ | 0.25 hours |
| Recovery cycle $\Gamma$ | 2.25 hours |

The initial SOC and terminal target should use the efficiency-aware centering
rule preserved by the reference configuration:

$$
y^{\mathrm{center}}
=
\frac{\overline y+\eta_c\eta_d\underline y}
{1+\eta_c\eta_d}.
$$

Historical day-ahead and reserve-market data should be supported by the
library-owned ENTSO-E adapter described above. The initial real-data reference
case should use a bounded historical period rather than the baseline's complete
multi-year dataset. Its persisted artifact must have explicit provenance and
redistribution status. The high-resolution regulation trace remains a separate
source contract until the resolution and meaning of relevant ENTSO-E balancing
documents are proven equivalent to the required FCR activation signal.

## Recommended Next Features

### 1. BESS FCR Stacked-Service Market and Simulator

**Suggested identifier:** `010-bess-stacked-services`

This should be the immediate next feature because every subsequent optimization
or learning method depends on trustworthy service and settlement semantics. Its
first concrete profile should be the robust-storage-bidding day-ahead-plus-FCR
case described above, while keeping the underlying types sufficiently generic
for later market adapters.

Its broad scope should include:

- an authenticated `open_energy_lab.market.entsoe` producer accepting a valid
  API token and an explicit start/end period;
- normalized, versioned market-data artifacts that decouple retrieval from
  simulator execution;
- day-ahead energy prices;
- symmetric FCR capacity prices and optional activation-energy payments;
- one symmetric FCR commitment per configured market block;
- a normalized regulation activation signal;
- hourly energy, 15-minute robust-state, four-hour FCR, and 10-second replay
  time grids;
- energy baseline, regulation request, and combined battery dispatch;
- charge/discharge and SOC headroom;
- requested versus delivered regulation;
- tracking error, saturation, and non-performance events;
- energy revenue, regulation revenue, and explicit penalty decomposition; and
- battery throughput plus a documented first-order degradation-cost proxy.

The first release should be real-data enabled and offline reproducible. It
should support one battery, the French day-ahead energy product, and one
symmetric FCR product over a caller-selected historical interval. A selected
French day fetched from ENTSO-E should provide the end-to-end demonstration;
its persisted artifact should provide the routine offline replay. A small
deterministic scenario should remain alongside it to make the physical and
settlement equations independently testable.

An explicit live `fetch` or `refresh` operation is in scope, but implicit
network access during every simulator execution is not. Generic pan-European
coverage, continuous data services, detailed electrochemical aging, network
constraints, and learned control should remain out of scope. If ENTSO-E lacks
the required historical FCR price or high-resolution activation series for the
selected interval, the module must report that limitation and use a declared
RTE or baseline-data adapter rather than silently substituting another series.

Useful deterministic baselines are:

- the existing arbitrage-only controller;
- a regulation-only controller that maintains SOC headroom; and
- a stacked heuristic that performs arbitrage only when regulation commitments
  remain deliverable.

The simulator should support detailed regulation-signal replay while allowing
the scheduler to operate at a coarser interval. This keeps high-frequency
physical validation separate from the size of an operational optimization
model.

### 2. aFRR And mFRR Market Profiles And Simulator

**Suggested identifier:** `011-afrr-mfrr-services`

This should follow the FCR vertical slice and extend its common market-data,
battery-dispatch, and settlement contracts without changing the validated FCR
semantics. It should support separate aFRR and mFRR profiles rather than one
generic "frequency regulation" mode.

Its broad scope should include:

- ENTSO-E ingestion and canonical artifact fields for available aFRR and mFRR
  capacity, bid, price, activation, and settlement series;
- separate upward and downward capacity and balancing-energy commitments;
- an automatic activation trajectory and tracking contract for aFRR;
- scheduled and direct activation-event contracts for mFRR;
- product-specific activation time, ramp, duration, delivery, and
  non-performance semantics;
- capacity and activated-energy revenue decomposition;
- fixed valid schedules plus deterministic product-specific heuristics; and
- one bounded real-data demonstration for each product where source coverage
  permits it.

The feature should fail explicitly when an ENTSO-E series is unavailable,
aggregated beyond the required simulator semantics, or inconsistent with the
selected market profile. It should allow an activation trace or event sequence
to be supplied through the canonical artifact contract when the Transparency
Platform does not expose the required operational resolution.

Joint multi-product optimization, cross-border platform modeling, continuous
production data services, and detailed national prequalification rules should
remain out of scope. Those require stable FCR, aFRR, and mFRR simulation and
settlement evidence first.

### 3. Robust Arbitrage-FCR Bidding

**Suggested identifier:** `012-robust-storage-bidding`

After fixed schedules and heuristic controllers are validated, add the
Pyomo/HiGHS MILP restriction and relaxation that jointly choose:

- the energy-market charge/discharge baseline;
- one symmetric FCR capacity commitment per market block;
- the SOC trajectory and reserve headroom; and
- an optional terminal SOC target.

The objective should combine day-ahead revenue, FCR capacity revenue, and
explicit feasibility penalties. The optimization should enforce deliverability
for all signals in the activation uncertainty set; it should not optimize using
the realized regulation trace. Exact replay against that trace validates the
selected bids afterward. The optional exact Gurobi formulation provides parity
evidence, while the required HiGHS restriction remains the supported open-source
solve path.

### 4. Rolling And Intraday Robust Bidding

**Suggested identifier:** `013-rolling-fcr-bidding`

Receding-horizon behavior becomes relevant after the market simulator and
robust optimizer are stable. It should preserve committed day-ahead and FCR
bids, update SOC from realized activation, and periodically allocate intraday
adjustments using leakage-free information about:

- energy prices;
- FCR prices and already committed blocks;
- the remaining activation budget and observed activation history;
- load and PV when the BESS is behind the meter; and
- expected regulation-signal energy bias or mileage.

The optimizer should operate at the market scheduling timescale. A lightweight
real-time tracker should follow the actual FCR signal between updates. Generic
forecast-aware MPC can later be exposed as an abstraction over this concrete
rolling robust-bidding workflow. Any oracle-price run should remain a labelled
upper-bound experiment rather than a deployable comparator.

### 5. TPM-Backed BESS Design and Policy Selection

**Suggested identifier:** `014-tpm-bess-service-planning`

This feature would reuse the 009 pipeline with stacked-service simulation rows.
A dataset could relate:

- BESS power and energy capacity;
- efficiency and degradation-cost parameters;
- robust bidding formulation and uncertainty-budget parameters;
- day-ahead and FCR market conditions;
- activation-signal energy, budget use, and saturation characteristics;
- total profit, tracking performance, and SOC saturation; and
- an explicit binary service-failure event.

The robust and probabilistic layers should remain complementary. Robust bidding
guarantees deliverability for all signals inside its assumed set. The TPM
models performance across market regimes, battery designs, policy choices, and
possible misspecification of that set. The initial chance constraint could
retain 009's one-target boundary, for example:

```text
P(FCR non-delivery > tolerance | BESS design, robust policy) <= epsilon
```

The planner could then select a minimum-cost BESS design or policy that meets a
service-reliability requirement. Later work could add multiple independent
constraints for profitability, regulation delivery, and degradation.

### 6. Learned and RL Controllers

**Suggested identifier:** `015-bess-policy-learning`

Once the simulator, heuristic baselines, robust bidding bounds, and rolling
optimizer are available, RL or other learned controllers can be evaluated
fairly through the same controller and information contracts.

The first learned-control feature should be single-site, CPU-default, and
offline. It should use the same observations, forecasts, action limits, market
settlement, and evaluation episodes as the rolling robust bidder. Federated or
multi-site learning should follow only after a multi-site simulator contract
exists.

## Recommended Dependency Order

```text
ENTSO-E API -----> 010 market-data producer and stacked-service simulator
                              ^                 |
                              |                 v
                    009 TPM planning     011 aFRR/mFRR market
                        foundation       profiles and simulator
                              ^                 |
                              |                 v
                              |          012 robust FCR bidding
                              |          restriction/relaxation
                              |                 |
                              |                 +--------------------+
                              |                 v                    v
                              +------ 013 rolling FCR bidding   014 TPM design/
                                                |               policy planning
                                                v
                                      015 learned/RL controllers
```

Feature 010 should remain the smallest complete FCR vertical slice. Feature 011
then generalizes the validated market-data and simulator contracts to aFRR and
mFRR without delaying FCR validation or merging distinct product semantics.
Feature 012 adds robust FCR optimization only after the fixed-schedule
simulation path is trustworthy. A later optimization feature may stack all
three reserve products once their individual settlement and activation
contracts are validated.

## Initial Validation Priorities

Before adding rolling/intraday optimization or TPM fitting, the stacked-service
simulator should prove:

1. Zero regulation commitment reproduces the existing arbitrage semantics.
2. A zero energy baseline permits regulation-only operation and settlement.
3. Combined energy and regulation requests never exceed battery power limits.
4. SOC limits correctly reduce or prevent regulation delivery.
5. Multi-rate aggregation conserves energy across regulation substeps.
6. Energy revenue, regulation revenue, penalties, and degradation cost remain
   separately inspectable.
7. An authenticated ENTSO-E fetch for an explicit French period produces a
   canonical artifact without persisting or logging the API token.
8. Repeated offline evaluation of a recorded real-data artifact produces
   identical traces and totals without network access.
9. UTC conversion, local delivery periods, daylight-saving transitions,
   missing intervals, duplicates, and source revisions are handled explicitly.
10. Existing simulator and controller fixtures remain unchanged.
11. The required MILP restriction is feasible under exact signal replay.
12. The restriction, optional exact formulation, and relaxation respect
    $z_{\mathrm{restriction}}\le z_{\mathrm{exact}}\le
    z_{\mathrm{relaxation}}$ within documented solver tolerances.

Before claiming the aFRR/mFRR extension complete, Feature 011 should also
prove:

1. aFRR automatic activation and mFRR activation events use distinct typed
   inputs and cannot be silently interchanged;
2. upward and downward delivery, capacity revenue, activated-energy revenue,
   and non-performance remain separately inspectable;
3. zero activation preserves the committed baseline and produces no balancing
   energy settlement;
4. product-specific ramp, activation-time, duration, power, and SOC violations
   are detected deterministically; and
5. missing or insufficiently resolved ENTSO-E series fail with source and
   period diagnostics rather than being imputed as operational signals.

## Decision Summary

- Feature 009 conceptually reproduces the paper's simulator-SPN-MILP planning
  method and is sufficient as the probabilistic planning foundation.
- Exact reproduction of every paper experiment is not a roadmap requirement.
- Oracle optimization is valuable as validation and an upper bound, not as the
  primary deployable-controller comparison.
- The robust-storage-bidding day-ahead-plus-FCR case should be the first
  concrete market profile rather than an unspecified regulation product.
- Feature 010 should include an authenticated ENTSO-E market-data producer,
  initially for France, which retrieves caller-selected historical periods and
  emits a reusable canonical artifact.
- Feature 011 should be the immediate market-profile follow-up, extending the
  same data and simulator boundaries to aFRR automatic activation and mFRR
  scheduled/direct manual activation without weakening the FCR contract.
- aFRR and mFRR are separate products with different activation, timing, and
  settlement semantics; they must not be represented as aliases of the FCR
  signal.
- ENTSO-E access should be explicit through `fetch` and `refresh` operations;
  routine simulation, optimization, and testing should default to offline
  artifact consumption rather than fetching on every execution.
- A recorded historical artifact is a real-data fixture, not a synthetic-data
  limitation. A separate small deterministic case remains valuable for
  inspecting equations and detecting regressions.
- The high-resolution FCR activation trace must remain source-explicit until
  ENTSO-E data is verified to match the required resolution and semantics.
- Generic forecast-aware MPC is relevant to the end goal, but rolling robust
  FCR bidding is the better next operational abstraction.
- The immediate missing capability is a validated BESS service-stacking model
  covering arbitrage, regulation commitments, real-time delivery, settlement,
  headroom, and degradation.
- Once those semantics exist, robust bidding, rolling/intraday optimization,
  TPM-backed design selection, and learned controllers can be developed and
  compared on a common foundation.
