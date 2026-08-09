# Value capture and profit-model design

This reference prevents a common error: treating growth, premiumization, cost reduction, or funding as the profit model. It uses original generic pattern families rather than reproducing any proprietary catalogue.

## 1. Definition

A value proposition explains customer value. A profit model explains how the enterprise captures a sustainable share of that value as profit and cash.

A complete value-capture architecture states:

1. customer outcome and willingness-to-pay logic;
2. measurable value metric;
3. payer and charging unit;
4. price formula and pricing mechanism;
5. contract terms and risk sharing;
6. revenue timing;
7. unit economics and cash conversion;
8. strategic control that protects the economics.

The following are inputs or adjacent plans, not complete profit models:

| Content | Proper place | Missing value-capture question |
|---|---|---|
| Revenue growth, volume, market expansion | Growth plan | How does value become unit profit? |
| Premiumization or mix upgrade | Offering/portfolio | Which measurable value supports which price? |
| Cost reduction or utilization | Operating model | Who pays and under what contract? |
| R&D budget or financing | Resource plan | Why and how does the customer pay? |
| “Technology premium” or “service fee” | Pricing direction | Formula, unit, conditions, risk sharing, and margin logic |

## 2. Screen generic pattern families

State which library or family set is used. If the user provides a licensed taxonomy, record its exact version and keep it outside distributable skill files unless redistribution is authorized.

The built-in original families are:

1. **Customer-relationship economics** — profit follows problem ownership, retention, share of wallet, or lifecycle service.
2. **Product and portfolio economics** — profit follows differentiation, portfolio architecture, bundles, or cross-subsidy.
3. **Platform and network economics** — profit follows matching, transactions, participation, data, or network effects.
4. **Timing and lifecycle economics** — profit follows speed, scarcity windows, replacement cycles, or lifecycle timing.
5. **Installed-base and aftermarket economics** — profit follows a deployed base, consumables, maintenance, upgrades, or recurring service.
6. **Scale, cost, and experience economics** — profit follows utilization, procurement, learning, process advantage, or low-cost design.
7. **IP, standard, data, and brand economics** — profit follows defensible rights, certification, standards, trust, or information advantage.
8. **Value-chain-position economics** — profit follows control of a bottleneck, interface, route to market, aggregation point, or risk-bearing position.

Screen all applicable families using target-customer value, enterprise capability, observed industry evidence, cash characteristics, control points, and adoption/contract feasibility. Shortlist 3–5 candidates (at least two), and explain rejected alternatives.

A pattern is a hypothesis about where profit concentrates. It is not a label to paste onto an operating loop.

## 3. Keep three levels separate

1. **Profit pattern** — why profit tends to concentrate in a business structure.
2. **Value-capture mechanism** — the actual payer, charging unit, price formula, pricing/contract structure, and risk sharing.
3. **Profit economics** — how revenue minus variable/incremental cost, working capital, and risk produces contribution and cash return.

Required chain:

`customer value equation -> pattern screening -> primary/supporting pattern -> charging and contract -> unit economics -> profitability estimate -> validation test`

## 4. Design sequence

### Customer value equation

For each target customer:

`customer value = incremental revenue + avoided loss + working-capital improvement + risk reduction - adoption/switching cost`

Mark a component not applicable when justified; do not invent an amount. Translate the equation into observable metrics.

### Candidate comparison

For every candidate state the mechanism, fit, evidence, assumptions, prerequisites, control points, and rejection risk. Choose a primary pattern and supporting patterns only where their customer/product/transaction roles do not conflict.

### Value-capture mechanism

For every mechanism state linked pattern IDs, linked value-equation IDs, offer, target customer, value created, metric, payer, charging unit, price formula, pricing mechanism, contract/risk sharing, revenue timing, margin logic, and control point.

### Unit economics

Choose a meaningful unit—customer, product, tonne, project, transaction, account, or lifecycle—and cover revenue formula, variable/incremental cost, contribution, working capital and cash conversion, sensitivity, and break-even/payback. If unavailable, use directional/not_available with a gap and test.

### Separate growth and funding

Revenue bridges, capacity, expansion, and financing belong in `growth_and_funding_plan`. They cannot replace value-capture mechanisms, unit economics, or profitability estimates.

## 5. Review gate

Return REVISE when the design lacks customer value, candidate screening, a coherent selected architecture, payer/unit/formula/contract, margin and cash logic, unit economics, or validation for critical assumptions. The final design must answer:

> For which customer, because of which measurable value, through which charging unit and contract, protected by which control point, does the enterprise earn what unit profit and cash return?
