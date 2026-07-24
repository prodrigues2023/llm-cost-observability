# ADR-0004: Instrument at one boundary, not every call site

- **Status:** Accepted
- **Date:** 2026-07-24

## Context

Cost has to be captured somewhere in the code. The question is where — and the tempting answer, "at
each place we call the model", is the wrong one. Scattering capture across call sites means every new
call site is a new chance to forget the instrumentation, tag a dimension wrong, or compute cost with
a slightly different formula. The result is attribution that is inconsistent, incomplete, and
impossible to trust, because you can never be sure every call site did it the same way — or did it at
all.

The alternative is a single boundary that every model call already passes through — a gateway, a
client wrapper, a proxy — where cost is captured once, uniformly. Most systems already have such a
chokepoint, or benefit from introducing one for reasons beyond cost (retries, rate limiting, a single
place to swap providers).

Options considered:

1. **Instrument each call site.** Maximum context at each point, but capture is only as complete as
   the least disciplined call site, and consistency is impossible to enforce.
2. **A single boundary every call passes through.** One place computes cost and reads the dimensions
   from the propagated context. Complete and uniform by construction; requires the context to reach
   the boundary.
3. **A sidecar or network proxy outside the process.** Language-agnostic and fully decoupled, but the
   business dimensions (feature, tenant) are hardest to see from there — exactly the tags that matter
   most.

## Decision

**Cost is captured at a single instrumentation boundary that every model call passes through; call
sites propagate the attribution dimensions to it but do not compute cost themselves.**

- The boundary is the one place that turns a call into a cost event: it reads token counts, applies
  the price basis, and attaches the dimensions from the propagated context
  ([ADR-0002](./0002-attribute-at-the-call.md)).
- Call sites have one job: propagate the dimensions (feature, tenant, route, prompt version) into the
  context the boundary reads. They never compute or emit cost themselves.
- The boundary is failure-isolated and cheap: emitting a cost event must never add meaningful latency
  to, or be able to fail, the underlying call. Cost instrumentation that can break the request is
  worse than none.
- Where a network proxy is used for provider abstraction, the in-process boundary still owns the
  business dimensions the proxy cannot see, and the two are correlated rather than duplicated.

## Consequences

**Positive**

- Capture is complete and uniform: one implementation, one formula, one set of tags, applied to every
  call by construction — no call site can silently skip or diverge.
- A new call site gets cost instrumentation for free the moment it goes through the boundary, so
  coverage does not decay as the system grows.
- Centralising the price-basis logic means a pricing change is made once, not chased across the
  codebase.

**Negative**

- The boundary depends on the dimensions being propagated to it. A call site that fails to pass its
  tenant or feature produces attributed-to-unknown cost — the completeness is only as good as the
  context propagation feeding it.
- A single boundary is a single point that must be cheap and reliable. Done carelessly it adds latency
  to every call or, worse, becomes a way for the instrument to fail the request it was only meant to
  measure.
- Some genuinely useful local context at a call site is lost by the time execution reaches the
  boundary, so the dimension set is limited to what can be cleanly propagated — a reason to keep that
  set small ([attribution.md](../attribution.md)).
