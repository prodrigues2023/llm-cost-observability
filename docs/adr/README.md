# Architecture Decision Records

Decisions are numbered, immutable once accepted, and superseded rather than edited.
See [ADR-0001](./0001-record-architecture-decisions.md) for the process itself.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](./0001-record-architecture-decisions.md) | Record architecture decisions in ADRs | Accepted |
| [0002](./0002-attribute-at-the-call.md) | Attribute cost at the call, tagged with dimensions | Accepted |
| [0003](./0003-cost-per-outcome.md) | The unit is cost per successful outcome | Accepted |
| [0004](./0004-instrument-at-the-boundary.md) | Instrument at one boundary, not every call site | Accepted |
| [0005](./0005-budgets-and-alerts.md) | Budgets and anomaly alerts are first-class | Accepted |
| [0006](./0006-cost-event-schema-and-pricing-abstraction.md) | Cost-event schema and pricing abstraction | Accepted |

## How the accepted decisions fit together

They turn a bill into an instrument:

- **0002** captures cost **where the causal context exists** — at the call, tagged with the feature,
  tenant, and route that caused it. Miss this and no later query can reconstruct attribution.
- **0003** measures the **right unit** — cost per successful outcome — so retries and waste are
  visible instead of hidden in a token total.
- **0004** puts the capture at **one boundary** every call passes through, so attribution is
  consistent and complete rather than scattered and partial.
- **0005** makes cost **alertable** — a budget and an anomaly detector, so a cost regression pages
  someone like a latency regression does.
- **0006** makes 0002 through 0005 **implementable** — the exact cost-event fields, the outcome
  state machine 0003's denominator needs, and the provider-neutral pricing formula 0002 promised
  but did not specify.

The load-bearing decision is **0002**: attribution at the source is the one thing that cannot be
retrofitted. The unit (0003), the boundary (0004), and the alerts (0005) all assume the dimensions
were captured; without that capture, there is nothing to slice, and cost stays a monthly aggregate no
matter how good the dashboard is. 0006 is where all four stop being principles and become a schema a
producer can actually write.

## Template

```markdown
# ADR-XXXX: Title

- **Status:** Proposed | Accepted | Superseded by ADR-YYYY
- **Date:** YYYY-MM-DD

## Context

The forces at play: the requirement, the constraints, the options considered and why each
was or was not viable.

## Decision

What was decided, in the active voice. What was deliberately deferred.

## Consequences

**Positive** — what this buys.

**Negative** — what it costs, and what you will have to live with. An ADR with no negative
consequences has not been thought through.
```

## Disagreeing with a decision

Open an issue titled `ADR-XXXX: <your objection>`. Experience from running cost observability in
production — especially a dimension that turned out to matter more, or less, than expected — is the
most useful kind.
