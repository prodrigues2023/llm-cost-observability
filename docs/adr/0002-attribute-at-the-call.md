# ADR-0002: Attribute cost at the call, tagged with dimensions

- **Status:** Accepted
- **Date:** 2026-07-24

## Context

The central question of cost observability is not "how much did we spend" — the bill answers that —
but "what caused the spend". Answering it requires linking each unit of cost to the feature, tenant,
and route responsible. And that link is available at exactly one moment: when the call is made, in
the context that made it. After that, the token count and the price are just numbers with no memory
of why they existed.

Options considered:

1. **Reconstruct attribution from the bill.** Parse the provider invoice and try to allocate cost
   back to features. There is nothing in a token total that says which feature caused it; any
   allocation is a guess, and a coarse one.
2. **Reconstruct from application logs after the fact.** Join billing data against request logs by
   timestamp. Fragile, approximate, and it breaks the moment logs and billing granularity disagree —
   which they always do.
3. **Tag each call with its dimensions as it happens.** The calling context — which feature, which
   tenant, which route, which prompt version — is read at call time and attached to a cost event.
   Exact, because the causal link is captured while it still exists.
4. **Sample tagged calls.** Tag only a fraction to save storage. Cheaper, but it turns per-tenant and
   per-feature economics into estimates with error bars, undermining the point.

## Decision

**Every call emits a cost event tagged with its attribution dimensions, captured at the call from the
calling context — not reconstructed, not sampled.**

- The dimensions are the small, deliberate set in [attribution.md](./attribution.md): feature,
  tenant, route, model tier, outcome, prompt version.
- The tags are read from the calling context at the moment of the call, where that context is still
  present. This is why capture lives at the instrumentation boundary
  ([ADR-0004](./0004-instrument-at-the-boundary.md)) the call passes through, not in a batch job
  afterward.
- Attribution is complete, not sampled: every call is tagged, so per-tenant and per-feature totals
  are exact and reconcile against the bill, rather than being estimates.
- The event records token counts and a price basis, not a hard-coded price, keeping the design
  provider-neutral (the pricing abstraction is [Milestone 2](../../ROADMAP.md)).

## Consequences

**Positive**

- The question that matters — what caused the spend — is answerable exactly, because the causal
  context is captured while it exists rather than guessed at later.
- Complete capture means attributed totals reconcile with the bill, so the instrument is trusted
  rather than "roughly right".
- Tagging at one boundary keeps the dimensions consistent across every call, instead of each call
  site inventing its own.

**Negative**

- Every call now emits an event with several tags — a real volume of cost-attribution data to store
  and aggregate, with its own cost and cardinality to manage.
- The calling context must actually carry the dimensions to the boundary. A feature that fails to
  propagate its tenant or feature tag produces unattributed cost — an "unknown" bucket that, left
  unchecked, grows until the attribution is worthless.
- Capturing at the call couples cost instrumentation to the request path. It must be cheap and
  failure-isolated, because an instrument that adds latency or can fail a request is worse than the
  blindness it cures.
