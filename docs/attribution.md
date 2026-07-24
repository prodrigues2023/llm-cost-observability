# Attribution

Attribution is the whole game. A cost number you cannot slice is a bill; a cost number tagged with
who and what caused it is an instrument. This document defines the dimensions every cost event
carries and why each one earns its place. The decision to capture them *at the call* is
[ADR-0002](./adr/0002-attribute-at-the-call.md); this is what gets captured.

## The dimensions

Every cost event carries these tags, set at the call, never reconstructed later:

| Dimension | Answers | Why it earns a place |
| --- | --- | --- |
| **Feature** | Which product capability spent this? | The primary unit of "what costs what" — lets a team see a feature's economics |
| **Tenant** | Which customer / org / workspace? | Turns spend into per-customer unit economics — which accounts are profitable |
| **Route** | Which code path or endpoint? | Localises a regression to a change — the deploy that moved cost |
| **Model tier** | Which model / size was used? | Makes over-provisioning visible — a small task on a large tier |
| **Outcome** | Did the task this call belongs to succeed? | The denominator for cost-per-outcome ([ADR-0003](./adr/0003-cost-per-outcome.md)) |
| **Prompt version** | Which prompt produced this call? | Ties a cost change to a prompt change — the [prompt-registry](https://github.com/prodrigues2023/prompt-registry) link |

## Why these and not more

Every dimension is a cost of its own: cardinality to store, a tag to set correctly at every call
site, and a column someone has to keep meaningful. So the set is deliberately small and chosen so
each dimension answers a distinct operational question — and none is a free-form high-cardinality
field that would explode the storage
([cardinality is a real limit](https://github.com/prodrigues2023/k8s-observability-stack)).

Notably **out** of the standard set:

- **User ID.** High-cardinality, privacy-sensitive, and rarely the unit you act on — you tune a
  feature or a tenant, not a user. Attributing to a user is a special-case investigation, not a
  standing dimension.
- **Raw prompt text.** The cost event carries the prompt *version*, not its content — content is the
  registry's job and a privacy liability to copy into a cost store.
- **Timestamp bucket.** Time is an axis every query already has; it is not a tag.

## Attribution must be captured, not inferred

The reason attribution is an architectural decision and not a reporting feature: **if the tag is not
set when the call happens, the information is gone.** No query reconstructs "which feature caused this
call" from a token count and a price after the fact — the causal link existed only at the moment of
the call. This is precisely why attribution is captured at the instrumentation boundary
([ADR-0004](./adr/0004-instrument-at-the-boundary.md)) that every call passes through, where the
calling context is still available to read the dimensions from.

## What good attribution unlocks

- **Per-feature economics** — is this feature worth what it costs to run?
- **Per-tenant unit economics** — which customers cost more than they pay?
- **Regression localisation** — a cost jump narrowed to a route and a prompt version is a deploy you
  can point at, not a mystery in the total.
- **Honest model comparison** — cost per outcome by model tier, which is the only comparison that
  accounts for the retries a cheap-but-unreliable model incurs.
