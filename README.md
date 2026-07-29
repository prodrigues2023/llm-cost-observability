# LLM Cost Observability

> LLM spend is an operational signal, not a monthly surprise. Attribute every token to the feature,
> tenant, and request that caused it — and measure cost per successful outcome, not cost per token.
> Documented first, provider-neutral, implemented in the open.

[![Phase](https://img.shields.io/badge/phase-4%20validation-blue)](./ROADMAP.md)
[![ADRs](https://img.shields.io/badge/ADRs-6-green)](./docs/adr)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

Most teams learn what their AI features cost from the bill — one number, a month late, with no way to
say which feature, which tenant, or which change drove it up. By the time a cost regression is
visible, it has been live for weeks. The spend that a good latency dashboard would have caught in an
hour is invisible, because cost was never instrumented the way latency was.

The fix is to treat cost as a signal like any other: measured at the call, tagged with the
dimensions that let you attribute it, and watched with budgets and anomaly alerts. And to measure the
right thing — not tokens burned, but cost per successful outcome, so a "cheap" model that fails and
retries twice is correctly seen as the expensive one. This repository is the design for that.

**Português:** [README.pt-BR.md](./README.pt-BR.md)

---

![The console mid-retry-storm: an anomaly alert, a budget breach, and cost-per-outcome visibly spiking for checkout-assistant while total spend barely moves](./docs/screenshots/console.png)

## What is here today

| Area | Status | Link |
| --- | --- | --- |
| Context & scope | Done | [docs/context.md](./docs/context.md) |
| Cost model | Done | [docs/cost-model.md](./docs/cost-model.md) |
| Attribution dimensions | Done | [docs/attribution.md](./docs/attribution.md) |
| Instrumentation diagrams | Done | [docs/diagrams](./docs/diagrams) |
| UI prototype (design mockup) | Done | [▶ live demo](https://prodrigues2023.github.io/llm-cost-observability/prototype/) · [source](./docs/prototype) |
| Architecture Decision Records | 6 published | [docs/adr](./docs/adr) |
| Contracts — cost-event schema, outcome contract, pricing abstraction | Done | [docs/contracts](./docs/contracts) |
| Reference implementation — boundary, pricing, outcomes, budgets/anomalies, console | Done, 36 tests | [costkit](./costkit), [console](./console), [ROADMAP.md](./ROADMAP.md#milestone-3--reference-implementation) |
| Validation — cost regression, retry storm, context bloat, attribution reconciliation drills | Done, 4 more tests, enforced on every push | [docs/validation](./docs/validation), [ROADMAP.md](./ROADMAP.md#milestone-4--validation) |

## The idea

**Attribute cost at the call, to the dimensions that matter, and measure it per successful outcome.**
A token count and a price are not the interesting number; the interesting number is *this feature
cost this much for this tenant this week, and here is the change that moved it.* That requires three
things the bill does not give you:

- **Attribution at the source** ([ADR-0002](./docs/adr/0002-attribute-at-the-call.md)) — every call
  is tagged with the feature, tenant, and route that caused it, when it happens, not reconstructed
  afterward.
- **The right unit** ([ADR-0003](./docs/adr/0003-cost-per-outcome.md)) — cost per *successful* task,
  so retries, failures, and oversized context show up as the waste they are.
- **A single instrumentation point** ([ADR-0004](./docs/adr/0004-instrument-at-the-boundary.md)) —
  cost is captured at one boundary every call passes through, not sprinkled across call sites.

With those, cost becomes governable: **budgets and anomaly alerts** catch a regression the way a
latency alert does ([ADR-0005](./docs/adr/0005-budgets-and-alerts.md)), and a cost check can gate a
release before a pricey change ships.

## Spend is not waste

The most useful distinction this repository draws: **spend** is what a successful task legitimately
costs; **waste** is everything else billed on the way — a retry after a failure, context padded far
past what the task needed, a large model used where a small one would have answered. A cost dashboard
that shows only total spend hides the waste. One built on cost-per-outcome surfaces it — see
[the cost model](./docs/cost-model.md).

## Why documented first

Attribution is a decision you cannot retrofit cheaply. If calls are not tagged at the source, no
query reconstructs which feature or tenant drove the spend — the information was never captured. What
the dimensions are, where the single instrumentation point sits, and what "a successful outcome"
means for the unit cost are contracts that shape everything downstream, and they are far cheaper to
settle on paper than to backfill across a live system.

## Roadmap

Four phases, tracked as GitHub milestones. See [ROADMAP.md](./ROADMAP.md).

1. **Design** — the cost model, the attribution dimensions, the instrumentation point, the ADRs — done
2. **Contracts** — the cost-event schema, the outcome contract, and the pricing abstraction — done
3. **Reference implementation** — a boundary, pricing, outcome tracking, budgets/anomaly detection,
   and a dashboard, all real and tested (`make up`) — done, see
   [console/README.md](./console/README.md) for what's real versus stubbed
4. **Validation** — four drills (cost regression, retry storm, context bloat, attribution
   reconciliation), each a real run whose pass/fail claim is enforced by `make test` on every
   push — done, see [docs/validation](./docs/validation)

## Related

- [k8s-observability-stack](https://github.com/prodrigues2023/k8s-observability-stack) — the general metrics/logs/traces platform; this is the LLM-cost signal that rides on it
- [prompt-registry](https://github.com/prodrigues2023/prompt-registry) — where a cost check becomes a promotion gate, so a pricey prompt change is caught before it ships
- [agentic-patterns-catalog](https://github.com/prodrigues2023/agentic-patterns-catalog) — where the retry loops and multi-agent fan-out that drive cost-per-outcome up actually come from

## Author

Paulo Roberto Franco Rodrigues — AI Solutions Architect.
Recently designed enterprise AI frameworks and served on an AI architecture committee defining
the engineering standards that bring software discipline to AI delivery.
[LinkedIn](https://linkedin.com/in/paulo-roberto-franco-rodrigues)

## License

MIT — see [LICENSE](./LICENSE).
