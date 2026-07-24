# ADR-0001: Record architecture decisions in ADRs

- **Status:** Accepted
- **Date:** 2026-07-24

## Context

The choices that make cost observable — where to capture a cost event, what to tag it with, what unit
to divide by — are not obvious, and each one closes off alternatives that a future contributor might
otherwise reopen. If the reasoning lives only in the code and the dashboards, a reader cannot tell a
deliberate design from an accident, and a well-meaning change can quietly undo a decision without
knowing it was one.

The specific risk here is that cost instrumentation looks like plumbing, so its decisions are
especially prone to being treated as arbitrary and "cleaned up" by someone who did not know why the
attribution tag was set exactly where it was.

## Decision

**Record every architecturally significant decision as a numbered ADR**, using the format in
[the index](./README.md): Context, Decision, Consequences — with the negative consequences stated as
plainly as the positive.

- An ADR is immutable once accepted; a changed decision is a new ADR that supersedes the old.
- The decisions that shape the data — attribution at the call, the unit, the instrumentation
  boundary — are ADRs precisely because they are the ones most expensive to reverse after data has
  been collected under them.

## Consequences

**Positive**

- A reader sees why cost is captured where and how it is, and can challenge the reasoning rather than
  just the result.
- Superseding rather than editing keeps the evolution legible as pricing models and providers change.

**Negative**

- The discipline has a cost, and the temptation to skip an ADR for a "small" instrumentation choice
  is exactly how the record grows holes.
- A decision recorded once can be treated as settled longer than it should be, when the economics
  underneath it have shifted.
