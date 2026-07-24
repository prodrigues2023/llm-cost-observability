# ADR-0003: The unit is cost per successful outcome

- **Status:** Accepted
- **Date:** 2026-07-24

## Context

Once cost is attributed, the next question is what to divide it by — because a raw total, however
well attributed, still answers only "how much", never "how efficiently". The choice of denominator
decides what the dashboard makes visible and what it hides.

The obvious denominators are misleading. **Cost per token** is circular — it is roughly constant by
construction and tells you nothing about whether the tokens were well spent. **Cost per request**
counts a failed request and a successful one the same, so a system that fails and retries looks
identical to one that succeeds first time. Both hide the single most important efficiency fact: how
much you paid for work that actually succeeded.

A concrete case sharpens it. Model A is cheaper per token but fails a quarter of its calls, each
failure retried. Model B costs more per token but succeeds first time. On cost-per-token, A wins. On
cost per *successful outcome*, A is paying for a quarter of its work twice and B is often cheaper. The
per-token view does not just miss this — it actively recommends the wrong model.

## Decision

**The headline unit is cost per successful outcome: total attributed cost (spend plus waste) divided
by the number of successful task outcomes.**

- The denominator is *successful outcomes*, not calls and not tokens. A task that failed contributes
  its cost to the numerator and nothing to the denominator, so waste raises the unit cost — which is
  the whole point.
- An "outcome" is a task, which is usually several calls, not one call. The `outcome` dimension
  ([attribution.md](./attribution.md)) marks which calls belong to a task and whether it succeeded;
  defining that contract precisely is [Milestone 2](../../ROADMAP.md) work.
- Total spend is still shown — it answers "how much" and pays the bill — but always *beside* unit
  cost, never instead of it. Unit cost is what tells you whether a change helped.
- Model and pattern comparisons are made on cost per outcome, so the comparison accounts for the
  retries an unreliable option incurs ([cost-model.md](../cost-model.md)).

## Consequences

**Positive**

- Waste becomes visible. A retry storm, an abandoned-task spike, a reflection loop that runs long —
  all raise cost per outcome even when total spend looks flat, so they surface as regressions instead
  of hiding in the total.
- Model choice becomes honest. The unit that accounts for reliability is the only fair basis for "is
  the cheaper model actually cheaper", and it frequently says no.
- It aligns the cost metric with the business: what a *successful* piece of work costs is the number
  product and finance actually care about.

**Negative**

- It requires defining "a successful outcome", which is a genuine contract and a source of dispute. A
  task spanning several calls, partial successes, and asynchronous completion all make "did it
  succeed" less crisp than "did the call return".
- Attributing several calls to one outcome adds correlation work — the calls of a task must be tied
  together — which is more than just summing per-call costs.
- A wrong or gamed success definition corrupts the unit. If "success" is defined too loosely, waste
  hides again; too strictly, and normal variation looks like waste. The denominator is only as honest
  as the outcome contract behind it.
