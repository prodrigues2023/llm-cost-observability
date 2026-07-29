# ADR-0006: Cost-event schema and pricing abstraction

- **Status:** Accepted
- **Date:** 2026-07-29

## Context

Milestone 1 decided *that* cost is attributed at the call, measured per outcome, captured at one
boundary, and alertable ([ADR-0002](./0002-attribute-at-the-call.md) through
[ADR-0005](./0005-budgets-and-alerts.md)). None of those decisions specify the actual record a
call produces or how a token count becomes a currency amount — without that, "a producer and a
dashboard integrate consistently" (this repository's Milestone 2 goal) is not achievable, because
there is nothing precise for either side to agree on.

Two open questions, both genuinely hard to leave implicit:

1. **What exactly does a call emit?** Every dimension in [attribution.md](../attribution.md), plus
   token counts, plus enough to compute and later re-verify a cost, plus a way to correlate calls
   belonging to one task ([ADR-0003](./0003-cost-per-outcome.md)'s denominator). Get the field set
   wrong and either attribution is incomplete or the store is bloated with fields nobody queries.
2. **How does a token count become a cost, without hard-coding a provider?** ADR-0002 already
   committed to "tokens times a price basis, not a hard-coded price" as a principle; this decision
   is what a price basis concretely *is* and how it is looked up and versioned.

Options considered for the schema:

1. **A flat, ad hoc event shape**, fields added as needed. Fast to start, but "as needed" is how a
   schema drifts into inconsistency across producers — exactly what a contract exists to prevent.
2. **A precise, versioned schema and a companion outcome contract**, specified before any producer
   is built. Front-loads the design work Milestone 2 is for, and is the only option that lets a
   producer and a dashboard be built independently and agree.

Options considered for pricing:

1. **Hard-code a price list per provider in the boundary.** Simplest to start, and exactly the
   coupling ADR-0002 already ruled out — a provider or price change means editing code.
2. **A versioned, dated rate table keyed by an abstract `model_tier`,** looked up at call time and
   referenced by id from the cost event, never inlined as a raw number. Provider-neutral, and
   reproducible after a price change, at the cost of maintaining the table as a real artifact.

## Decision

**Two new contracts, both specified in full in this milestone:**

- **[cost-event-schema.md](../contracts/cost-event-schema.md)** — the exact fields a call emits:
  the six attribution dimensions from [attribution.md](../attribution.md) (`feature`, `tenant`,
  `route`, `model_tier`, `prompt_version`, plus `outcome_id` replacing a per-call outcome flag),
  token counts (`input_tokens`, `output_tokens`, `cached_input_tokens`), a reference to the price
  basis used (`price_basis_id`) and the cost it computed (`computed_cost`), an `attempt_number`
  that makes retries visible in the raw stream, and a per-call `call_status` distinct from the
  task-level outcome.
- **[outcome-contract.md](../contracts/outcome-contract.md)** — what `outcome_id` resolves to: a
  record with an explicit state machine (`pending → succeeded | failed | abandoned`), resolved
  exactly once by the task's owner (never the boundary, which cannot know whether a result was
  acceptable), with a mandatory resolution window so a task cannot stay `pending` — and therefore
  invisible to the denominator — forever.
- **[pricing-abstraction.md](../contracts/pricing-abstraction.md)** — a versioned, dated rate table
  entry (a "price basis") keyed by an abstract `model_tier`, with a fixed cost formula
  (`tokens × rate`, summed across input/output/cached) computed once at the boundary and never
  reimplemented per provider. Rates are append-only: a price change adds a new dated row rather
  than overwriting the old one, so a historical event's `computed_cost` stays reproducible and
  reconcilable against the bill after prices change.

The load-bearing design choice tying all three together: **`outcome_id` is a correlation key, not
a per-call boolean.** A call cannot know whether its task will ultimately succeed — only the task's
owner, later, can. Splitting "what happened on this call" (the cost event) from "did the task
succeed" (the outcome record) is what makes retries, partial completions, and long-running tasks
representable without corrupting the denominator.

## Consequences

**Positive**

- A producer and a dashboard built independently against these three documents agree on every
  field and every formula — this milestone's stated exit criterion — because there is nothing left
  implicit for either side to guess at.
- Retry waste, abandoned work, and partial success — the exact failure modes
  [cost-model.md](../cost-model.md) names — are all representable without special-casing, because
  `attempt_number`, the outcome state machine, and the resolution window were designed against
  those cases specifically, not added after the fact.
- Historical cost stays reproducible after a price change, which is what makes Milestone 4's
  reconciliation-against-the-bill exit criterion achievable at all.

**Negative**

- **The outcome contract's resolution window is a tuning parameter with no universal default.** Set
  it too short and legitimately long-running tasks are marked `abandoned` incorrectly; too long,
  and a genuinely abandoned task's cost sits invisible in `pending` for a long time. Milestone 3
  ships a default that will be wrong for some features.
- **The schema requires real propagation discipline.** `outcome_id`, like every attribution
  dimension, must reach the boundary from the call site; a task whose framework does not thread
  context cleanly to every call will produce `unattributed` events, the same completeness risk
  ADR-0002 already flagged, now doubled by needing the outcome correlation too.
- **The pricing abstraction's rate table is a real artifact someone must maintain.** It does not
  fetch prices automatically (by design, per
  [pricing-abstraction.md](../contracts/pricing-abstraction.md)'s "what this deliberately does
  not do"), so a provider price change that nobody updates the table for produces a
  `computed_cost` that is wrong until someone notices — a manual step where an automated one was
  deliberately rejected for auditability, trading convenience for control.
