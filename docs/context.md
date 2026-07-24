# Context and scope

## The problem

An AI feature's cost is real, variable, and — in most systems — invisible until the bill arrives. The
bill is one aggregate number, delivered weeks after the spend happened, with no breakdown by feature,
tenant, or request. So the questions that matter operationally have no answer: which feature is
expensive, which tenant is unprofitable, and — the one that actually bites — *which change made the
cost jump?*

The asymmetry with latency is stark. If a deploy doubled p99 latency, a dashboard would show it
within minutes and someone would roll it back. If the same deploy doubled cost per request — a bigger
model, a padded prompt, a retry loop that now fires twice — nothing shows it until the invoice, by
which point it has been live for a full billing cycle. Cost is as much an operational signal as
latency; it is simply never instrumented like one.

There is a second, subtler problem: even teams that track token spend usually track the wrong unit.
Total tokens burned says nothing about efficiency. A "cheaper" model that fails a quarter of the time
and retries is more expensive per *successful* task than the pricier model that succeeds first try —
but a tokens-burned dashboard shows the cheap model as the win. The right unit is cost per successful
outcome, and almost no one measures it.

This repository is the design for treating LLM cost as a first-class observable: attributed at the
call, tagged with the dimensions that let you slice it, measured per outcome, and watched with
budgets and anomaly alerts.

## Users

| User | Need |
| --- | --- |
| Engineer | See what a change did to cost-per-request the way they see what it did to latency |
| Product / finance | Attribute spend to a feature and a tenant, to know what is profitable |
| Architect | Compare models and patterns on cost per successful outcome, not sticker price |
| On-call | Get alerted on a cost anomaly before it becomes a month of overspend |

## In scope

- Attributing cost at the call, tagged with feature, tenant, and route
  ([ADR-0002](./adr/0002-attribute-at-the-call.md))
- The unit: cost per successful outcome, not per token
  ([ADR-0003](./adr/0003-cost-per-outcome.md))
- A single instrumentation boundary every call passes through
  ([ADR-0004](./adr/0004-instrument-at-the-boundary.md))
- Budgets and anomaly alerts on cost as a signal
  ([ADR-0005](./adr/0005-budgets-and-alerts.md))
- The distinction between spend and waste ([cost-model.md](./cost-model.md))

## Explicitly out of scope

Deliberate exclusions:

- **General infrastructure observability.** Metrics, logs, and traces for services and clusters are
  the [k8s-observability-stack](https://github.com/prodrigues2023/k8s-observability-stack)'s subject.
  This repository is specifically the LLM-cost signal, which rides on such a platform.
- **A specific provider's pricing.** Prices change and differ per provider; this repository defines a
  pricing *abstraction* — token counts times a price basis — not a hard-coded price list.
- **Model selection advice.** Which model to use for a task is a decision this instrument *informs*
  (by measuring cost per outcome) but does not make. It is not a benchmark or a recommendation.
- **FinOps for the whole cloud bill.** Compute, storage, and network cost governance is a broad
  discipline; this is scoped to the LLM-call portion of spend.
- **Rate limiting and quota enforcement.** Stopping a tenant from spending is a control layered on top
  of this visibility; this repository measures and alerts, it does not throttle.

## Key constraints

1. **Attribution happens at the source.** A cost event is tagged with its dimensions when the call
   happens; nothing reconstructs attribution from a bill later — see
   [ADR-0002](./adr/0002-attribute-at-the-call.md).
2. **The unit is cost per successful outcome.** Retries, failures, and waste are visible because the
   denominator is successful tasks, not tokens — see [ADR-0003](./adr/0003-cost-per-outcome.md).
3. **One instrumentation point.** Cost is captured at a single boundary every call passes through,
   not scattered across call sites — see [ADR-0004](./adr/0004-instrument-at-the-boundary.md).
4. **Cost is alertable.** Budgets and anomaly detection make a cost regression page someone, like a
   latency regression does — see [ADR-0005](./adr/0005-budgets-and-alerts.md).
5. **Provider-neutral.** A token count becomes a cost through a pricing abstraction, so no provider
   is hard-coded into the design.

## Related documents

- [Cost model](./cost-model.md) — what drives cost, and spend versus waste
- [Attribution](./attribution.md) — the dimensions every cost event carries
- [Diagrams](./diagrams) — the instrumentation boundary and the attribution flow
- [ADRs](./adr) — the decisions and their reasoning
