# The cost model

The purpose of this document is to name what actually drives LLM cost, and to separate the cost a
task legitimately incurs from the cost wasted around it. A dashboard built on this distinction shows
you where to act; one built on total spend only shows you that spend went up.

## What drives the cost of one call

A single call's cost is, in the abstract, its token volume times a price basis
([ADR-0002](./adr/0002-attribute-at-the-call.md)). The parts:

| Component | What it is | What inflates it |
| --- | --- | --- |
| Input tokens | Everything sent to the model | Padded context, whole documents where a snippet would do, long histories |
| Output tokens | Everything generated | Verbose formats, no length bound, re-generating what was asked before |
| Cached input | Input served from a cache at a lower basis | Absent when the call pattern defeats caching |
| Price basis | Cost per token, per direction, per model tier | A larger model tier for a task a smaller one handles |

The design stays provider-neutral: it records the token counts and the *basis*, and computes cost
from them. It does not hard-code any provider's numbers — see the pricing abstraction in
[Milestone 2](../ROADMAP.md).

## Spend versus waste

The load-bearing distinction. Of everything billed for a task:

- **Spend** is what the *successful* path legitimately costs — the input the task genuinely needed,
  the output it genuinely produced, once.
- **Waste** is everything else billed on the way to that outcome.

Common forms of waste, all invisible on a total-spend chart and all visible on a cost-per-outcome one
([ADR-0003](./adr/0003-cost-per-outcome.md)):

| Waste | What it looks like | Why total-spend hides it |
| --- | --- | --- |
| Retry waste | A call failed and ran again — sometimes several times | The retries are just more spend in the total |
| Context bloat | Far more input sent than the task needed | Higher input tokens read as "a big task" |
| Model over-provisioning | A large tier used where a small tier answers | Looks like normal cost for that tier |
| Abandoned work | Tokens spent on a task the user dropped or that errored out | Counted as spend though nothing succeeded |
| Reflection / fan-out overrun | An agent loop or multi-agent tree that ran long | Every extra step is billable and looks productive |

The last row is why this repository points back at the
[agentic-patterns-catalog](https://github.com/prodrigues2023/agentic-patterns-catalog): the retry
loops, reflection cycles, and orchestrator fan-out described there are exactly the control-flow
choices that drive cost-per-outcome up, and a runaway loop is a cost incident as much as an
availability one.

## The unit: cost per successful outcome

```
                total cost attributed to a task (spend + waste)
cost per outcome = ───────────────────────────────────────────────
                        number of successful outcomes
```

This is the number worth putting on a dashboard. It rises when waste rises even if spend looks flat,
so it catches a retry storm that a total-spend chart sleeps through. It also makes model and pattern
comparisons honest: a cheaper-per-token model that fails and retries has a *higher* cost per outcome,
which is the truth a per-token view inverts.

Defining "a successful outcome" is a real contract — a single call is rarely the unit; a task is
usually several calls, and success is a property of the task. That contract is
[Milestone 2](../ROADMAP.md) work; this document establishes only that the outcome, not the token, is
the denominator.

## What this changes about a dashboard

- **Slice by the attribution dimensions** ([attribution.md](./attribution.md)), never just a global
  total — a global number cannot tell you where to act.
- **Show unit cost next to total spend**, always. Total spend answers "how much"; unit cost answers
  "how efficiently", and only the second tells you whether a change was good.
- **Treat a unit-cost spike as an incident**, with a budget and an alert behind it
  ([ADR-0005](./adr/0005-budgets-and-alerts.md)), the same way a latency spike is treated.
