# Contracts

Milestone 1 decided the architecture. These documents specify the formats precisely enough that a
producer (the instrumentation boundary) and a consumer (a dashboard, an alert) built independently
agree on every field.

| Contract | Specifies |
| --- | --- |
| [Cost-event schema](./cost-event-schema.md) | The exact record a call emits: dimensions, tokens, price reference, computed cost |
| [Outcome contract](./outcome-contract.md) | What a "task" is, its state machine, who resolves it and when |
| [Pricing abstraction](./pricing-abstraction.md) | How a token count becomes a cost, provider-neutral and versioned |

Backed by [ADR-0006](../adr/0006-cost-event-schema-and-pricing-abstraction.md).

## How these compose

- The **cost-event schema** is what the instrumentation boundary
  ([ADR-0004](../adr/0004-instrument-at-the-boundary.md)) writes for every call.
- Its `outcome_id` field is a correlation key into the **outcome contract** — the record that
  answers "did the task this call belongs to succeed", which is what makes
  [ADR-0003](../adr/0003-cost-per-outcome.md)'s cost-per-outcome computable at all.
- Its `price_basis_id` field is a reference into the **pricing abstraction**'s rate table — what
  turns `input_tokens`/`output_tokens`/`cached_input_tokens` into `computed_cost` without a
  provider hard-coded anywhere in the design.

A reviewer checks a Milestone 3 producer against these three documents field by field: every
required field present, every reference resolvable, every computed value reproducible from its
inputs — the same test [aws-serverless-blueprints](https://github.com/prodrigues2023/aws-serverless-blueprints/tree/main/docs/contracts)'s
contracts are checked against.

## Related

- [docs/adr](../adr) — the decisions these contracts implement
- [Attribution](../attribution.md) — the dimensions the cost-event schema carries
- [Cost model](../cost-model.md) — spend versus waste, which the outcome contract and
  `attempt_number` make computable
- [ROADMAP.md](../../ROADMAP.md) — Milestone 3 builds a reference implementation against these
  contracts
