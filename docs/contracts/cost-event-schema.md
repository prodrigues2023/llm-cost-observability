# Cost-event schema

**What the instrumentation boundary emits for every call, and nothing else.**
[ADR-0004](../adr/0004-instrument-at-the-boundary.md) put capture at one boundary; this is the
exact record that boundary produces, so a producer and a dashboard built independently agree on
every field.

## The event

| Field | Type | Set by | Notes |
| --- | --- | --- | --- |
| `event_id` | UUID | Boundary | Unique per call. Never reused, even for a retry. |
| `outcome_id` | string | Propagated context | The correlation key tying this call to the task it belongs to — see [outcome-contract.md](./outcome-contract.md). Required; a call with no `outcome_id` is not attributable to an outcome and is itself a data-quality defect to alert on. |
| `timestamp` | RFC 3339 | Boundary | When the call was made, not when the event was flushed to the store. |
| `feature` | string | Propagated context | [attribution.md](../attribution.md)'s dimension. Required. |
| `tenant` | string | Propagated context | Required. |
| `route` | string | Propagated context | Required. |
| `model_tier` | string | Propagated context | An abstract label (e.g. `large`, `small`), not a provider model string — see [pricing-abstraction.md](./pricing-abstraction.md). Required. |
| `prompt_version` | string | Propagated context | Required. `"unversioned"` is a valid explicit value; empty/missing is not — see "Attribution must be captured, not inferred" in [attribution.md](../attribution.md). |
| `attempt_number` | integer, ≥1 | Propagated context or boundary | 1 for the first attempt at a step; incremented for a retry of the *same* step. This is what makes retry waste ([cost-model.md](../cost-model.md)) visible in the raw event stream, not just in the aggregate. |
| `input_tokens` | integer, ≥0 | Boundary, from the provider response | |
| `output_tokens` | integer, ≥0 | Boundary, from the provider response | |
| `cached_input_tokens` | integer, ≥0 | Boundary, from the provider response | Subset of `input_tokens` served at the cached rate; `0` when the provider reports no cache hit. |
| `price_basis_id` | string | Boundary, via the pricing abstraction | Identifies the exact rate table version used — see [pricing-abstraction.md](./pricing-abstraction.md). Never a raw number inlined here; always a reference, so a rate correction doesn't require rewriting history. |
| `computed_cost` | decimal | Boundary | `input_tokens × rate_in + output_tokens × rate_out + cached_input_tokens × rate_cached`, using `price_basis_id`'s rates at write time. Stored, not recomputed on every query — see "why store the computed value" below. |
| `call_status` | enum: `ok`, `error` | Boundary | Whether *this call* returned successfully. Independent of the task-level outcome — a call can `error` and still belong to a task that eventually `succeeded` via a later attempt. |

## What is deliberately not a field

- **Outcome success/failure.** That lives on the outcome record ([outcome-contract.md](./outcome-contract.md)), addressed by `outcome_id`, not duplicated onto every call — a task's success is known only once, not once per call, and is frequently known *after* the last call.
- **Raw prompt or response text.** Per [attribution.md](../attribution.md#why-these-and-not-more), content is the [prompt-registry](https://github.com/prodrigues2023/prompt-registry)'s job and a privacy liability here.
- **User ID.** Excluded from the standing dimension set for the same reason attribution.md excludes it — high-cardinality, privacy-sensitive, and not the unit anyone acts on.
- **A raw price number.** Only `price_basis_id` — see the versioning rationale in [pricing-abstraction.md](./pricing-abstraction.md).

## Why store the computed value, not just the inputs

`computed_cost` is written once, at emission, from the `price_basis_id` in effect at that moment —
not recomputed later from `input_tokens`/`output_tokens` against whatever the *current* rate table
says. A rate correction or a provider price change must not silently rewrite the cost of every
historical event; each event's cost is what was actually true when the call happened. This is what
[ADR-0002](../adr/0002-attribute-at-the-call.md)'s "attribute at the call, not reconstructed"
principle means applied to price, not only to the attribution tags.

## Validity rules a producer must satisfy

- Every required field is present; there is no default for a missing `feature`, `tenant`, or
  `route` — an event with one missing is written to an explicit `unknown` bucket for that field,
  never silently dropped or blank, so the gap is visible and countable (per
  [ADR-0002](../adr/0002-attribute-at-the-call.md)'s negative consequence about attribution decay).
- `cached_input_tokens ≤ input_tokens`.
- `computed_cost` is non-negative and consistent with `price_basis_id`'s rates — a consumer
  validating ingestion should be able to recompute it from the other fields and get the same
  number, as a check, even though the boundary is the source of truth for what was written.

## Related

- [Outcome contract](./outcome-contract.md) — what `outcome_id` resolves to and when
- [Pricing abstraction](./pricing-abstraction.md) — what `price_basis_id` refers to
- [ADR-0006](../adr/0006-cost-event-schema-and-pricing-abstraction.md) — the decision this schema implements
