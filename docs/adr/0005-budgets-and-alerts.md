# ADR-0005: Budgets and anomaly alerts are first-class

- **Status:** Accepted
- **Date:** 2026-07-24

## Context

Attribution and a good unit make cost *visible*, but visibility alone still relies on someone looking
at a dashboard at the right moment. The failure this repository exists to prevent — a cost regression
running live for weeks — happens precisely in the gap between "the data would have shown it" and
"someone looked". Latency solved this long ago: nobody watches a latency dashboard continuously; an
alert watches it for them. Cost deserves the same and rarely gets it.

Two kinds of cost problem need catching, and they are different. A **budget breach** is a threshold
crossed — a tenant or feature exceeding an expected spend or unit cost. An **anomaly** is a sudden
change regardless of absolute level — cost per outcome doubling after a deploy, well under any budget
but clearly a regression. A system with only budgets misses the regression that stays under the cap;
one with only anomaly detection misses the slow, steady climb that never spikes.

## Decision

**Cost is watched by both budgets and anomaly detection, as first-class alerting on the attributed,
per-outcome metrics — not a report someone reads.**

- **Budgets** are set per dimension ([attribution.md](../attribution.md)) — a feature's expected unit
  cost, a tenant's expected spend — and a breach alerts. Budgets encode intent: "this feature should
  cost about this much".
- **Anomaly detection** watches for sudden change in cost per outcome
  ([ADR-0003](./0003-cost-per-outcome.md)) independent of any threshold, so a post-deploy regression
  that stays under budget is still caught.
- **Alerts fire on the per-outcome unit, not just total spend**, so a retry storm — flat spend,
  rising unit cost — pages someone. This is the case a total-spend budget sleeps through entirely.
- **A cost check can gate a release.** The same signals feed a promotion gate, so a change that
  raises unit cost past a bar is caught before it ships — the [prompt-registry](https://github.com/prodrigues2023/prompt-registry)
  link, where a pricey prompt change is stopped at promotion rather than found on the bill.

## Consequences

**Positive**

- A cost regression pages someone in minutes, closing the weeks-long gap between spend and discovery
  that is the entire motivation for the repository.
- Two detectors cover two distinct failures: budgets catch crossing a known line, anomaly detection
  catches an unexpected change under the line. Neither alone is enough.
- Feeding a promotion gate turns cost from a thing you observe after the fact into a thing you can
  prevent before it ships.

**Negative**

- Alert tuning is a standing burden. Budgets set too tight and anomaly detection too sensitive
  produce noise, and a noisy cost alert is ignored exactly like a noisy latency alert — at which
  point it protects nothing.
- Anomaly detection on cost is genuinely hard: legitimate traffic swings (a launch, a big customer,
  a weekday pattern) look like anomalies, and distinguishing them from regressions needs baselining
  the design must not pretend is trivial.
- A cost gate on releases adds friction and can block a change that is worth its extra cost. The gate
  must express "worth it" somehow, or it becomes a veto on every improvement that happens to cost
  more.
