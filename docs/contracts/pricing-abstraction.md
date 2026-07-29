# Pricing abstraction

**How a token count becomes a cost without a provider's price list hard-coded into the design.**
[cost-model.md](../cost-model.md) named the price basis as one of the components of a call's cost;
this document specifies it precisely enough to implement, per
[ADR-0002](../adr/0002-attribute-at-the-call.md)'s "provider-neutral" constraint.

## The price basis

A price basis is a versioned, dated rate table entry — never a number inlined at a call site or
in the boundary's code:

| Field | Type | Notes |
| --- | --- | --- |
| `price_basis_id` | string | What a cost event's `price_basis_id` ([cost-event-schema.md](./cost-event-schema.md)) refers to. Opaque and stable — a rate correction gets a *new* id, it never mutates an existing one. |
| `model_tier` | string | The same abstract label a cost event carries — `large`, `small`, etc. Not a provider's model string; see "Why `model_tier` is abstract" below. |
| `currency` | string | ISO 4217 code (`USD`, ...). A deployment mixing currencies keeps them distinct rate tables, never converts inline in the boundary. |
| `rate_input` | decimal | Cost per input token, at this tier, in `currency`. |
| `rate_output` | decimal | Cost per output token. |
| `rate_cached_input` | decimal | Cost per cached input token — typically lower than `rate_input`; a provider with no cached-rate concept sets this equal to `rate_input`. |
| `effective_from` | RFC 3339 | When this rate took effect. |
| `effective_to` | RFC 3339, nullable | When it stopped applying; null for the currently active rate. |
| `source` | string | Where the rate came from — a provider's published pricing page, a negotiated contract rate, a note. Free text, but required: a rate with no stated source is a rate nobody can audit later. |

## Computing a call's cost

Fixed, and identical for every provider and tier:

```
computed_cost = input_tokens          × rate_input
              + output_tokens         × rate_output
              + cached_input_tokens   × rate_cached_input
```

using the `price_basis_id` whose `[effective_from, effective_to)` window contains the call's
timestamp for the call's `model_tier`. This formula lives in exactly one place — the
instrumentation boundary ([ADR-0004](../adr/0004-instrument-at-the-boundary.md)) — never
reimplemented per provider or per call site.

## Why `model_tier` is abstract

`model_tier` is a label the *deployment* chooses (`large`, `small`, `reasoning`, whatever
vocabulary fits its own model choices) and maps, via the rate table, to whichever provider and
model string actually backs it. This is what keeps a provider swap from touching the schema or the
boundary's formula: change the rate table's `model_tier → provider model` mapping and the rate
row's `source`, and every downstream number — dashboards, budgets, historical comparisons keyed by
`model_tier` — keeps meaning the same thing before and after the swap. A schema that stored a raw
provider model string as the dimension instead would break every query the moment the provider or
model changed.

## Why rates are versioned and dated, not just "the current price"

Two reasons, both load-bearing:

1. **Historical reproducibility.** [cost-event-schema.md](./cost-event-schema.md) stores
   `computed_cost` at write time using the `price_basis_id` active then. Looking up "what did this
   call cost" a year later, after three price changes, must return the number that was true when
   the call happened — not today's rate applied retroactively. This is only possible if old rates
   are kept, dated, and referenced by id rather than overwritten.
2. **Reconciliation.** Milestone 4's exit criterion is that attributed cost reconciles with the
   provider's bill. Reconciling a month that spanned a rate change requires knowing which calls
   used which rate — impossible if the rate table only ever holds "the current price."

A rate table is append-only in effect: a price change adds a new `price_basis_id` row with a new
`effective_from` and closes the previous row's `effective_to`; nothing already written is edited.

## What this abstraction deliberately does not do

- **It does not fetch live prices from a provider API.** The rate table is populated deliberately
  (from a provider's pricing page, a contract, or a manual update) and reviewed like any other
  configuration change — an automatic feed is a way for a provider-side price change to silently
  alter every dashboard's meaning without anyone deciding that was wanted.
- **It does not average or blend rates across a mixed-rate period.** A call uses exactly one price
  basis, the one in effect at its timestamp; there is no interpolation.
- **It is not a cost estimator for a call that has not happened yet.** This is strictly the
  after-the-fact "given these token counts, what did this call cost" computation the boundary
  performs — pre-call cost estimation is a different, unaddressed problem.

## Related

- [Cost-event schema](./cost-event-schema.md) — where `price_basis_id` and `computed_cost` are written
- [Cost model](../cost-model.md) — the price basis as a driver of a call's cost
- [ADR-0006](../adr/0006-cost-event-schema-and-pricing-abstraction.md) — the decision this implements
