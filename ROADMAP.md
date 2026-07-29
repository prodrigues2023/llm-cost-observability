# Roadmap

Four milestones. Each ships something usable on its own.

Track these as GitHub Milestones.

---

## Milestone 1 — Design (docs only)

**Goal:** a reader understands why cost must be attributed at the call and measured per outcome,
before any code.

| Issue | Deliverable |
| --- | --- |
| Write context document | Problem, users, scope, explicit non-goals |
| Cost model | What drives cost, and spend versus waste |
| Attribution dimensions | The tags every cost event carries and why |
| Instrumentation diagrams | The single boundary and the attribution flow |
| ADR-0001 | Record architecture decisions in ADRs |
| ADR-0002 | Attribute cost at the call, tagged with dimensions |
| ADR-0003 | The unit is cost per successful outcome |
| ADR-0004 | Instrument at one boundary, not every call site |
| ADR-0005 | Budgets and anomaly alerts are first-class |

**Exit criteria:** a reader can explain why the bill is the wrong instrument and what to measure
instead, and every decision traces to attribution-at-the-source.

---

## Milestone 2 — Contracts

**Goal:** the formats are specified, so a producer and a dashboard integrate consistently.

| Issue | Deliverable | Status |
| --- | --- | --- |
| Cost-event schema | Tokens, price basis, dimensions, timestamp, outcome | Done — [cost-event-schema.md](./docs/contracts/cost-event-schema.md) |
| Outcome contract | What marks a call part of a successful task versus waste | Done — [outcome-contract.md](./docs/contracts/outcome-contract.md) |
| Pricing abstraction | How a token count becomes a cost without hard-coding a provider | Done — [pricing-abstraction.md](./docs/contracts/pricing-abstraction.md) |
| ADR-0006 | Cost-event schema and pricing abstraction | Done — [0006](./docs/adr/0006-cost-event-schema-and-pricing-abstraction.md) |

**Exit criteria met** — the three contracts compose rather than restating each other: the
cost-event schema's `outcome_id` is exactly the outcome contract's correlation key, and its
`price_basis_id` is exactly the pricing abstraction's rate-table reference. A reviewer checks a
Milestone 3 producer against the three documents field by field, the same test named in
[docs/contracts/README.md](./docs/contracts/README.md).

Backed by [ADR-0006](./docs/adr/0006-cost-event-schema-and-pricing-abstraction.md).

---

## Milestone 3 — Reference implementation

**Goal:** `make up` runs a boundary that emits cost events and a dashboard that attributes them.

| Issue | Deliverable | Status |
| --- | --- | --- |
| Instrumentation boundary | Capture tokens and dimensions at one pass-through point | Done — [costkit/boundary.py](./costkit/boundary.py) |
| Cost event pipeline | Enrich with price, store, aggregate | Done — [costkit/store.py](./costkit/store.py) |
| Attribution dashboard | Spend and unit cost by feature, tenant, route | Done — [console](./console) |
| Budget and alerting | A budget per dimension and an anomaly alert | Done — [costkit/budgets.py](./costkit/budgets.py) |
| Local environment | One command, stubbed model, synthetic traffic, no cloud account | Done — `make up` |

**Exit criteria met, and verified for real, not asserted.** 36 tests exercise the schema, outcome
state machine, pricing formula, boundary, synthetic traffic, and budget/anomaly detectors —
including a test that proves a retried task's cost per outcome is measurably higher than a clean
task's, computed from real `CostEvent`/`Outcome` rows, not a canned fixture. The console's own
"Trigger retry-storm demo" button reproduces the exit criterion live: spend for the affected
feature barely moves while its cost per outcome visibly spikes on the dashboard, and the
`AvailabilityFastBurn`-style budget/anomaly detectors both fire against that real data. Full
account in [console/README.md](./console/README.md).

**What Milestone 3 does not claim:** the model itself is stubbed — `costkit.stub_model.StubModelClient`
stands in for a real provider, per ROADMAP's own "stubbed model, synthetic traffic, no cloud
account" scope for this milestone. Swapping in a real provider client is the only change
[ADR-0004](./docs/adr/0004-instrument-at-the-boundary.md) says a real deployment needs to make.
The anomaly detector is a deliberately simple rolling-baseline ratio, not a statistical model —
[ADR-0005](./docs/adr/0005-budgets-and-alerts.md) already named that as unsolved work.

---

## Milestone 4 — Validation

**Goal:** prove the alerts and the unit cost catch the failures that a bill hides.

| Issue | Deliverable | Status |
| --- | --- | --- |
| Cost regression drill | Swap in a pricier path; assert the anomaly alert fires | Done — [cost-regression-drill.md](./docs/validation/cost-regression-drill.md) |
| Retry storm | Inject failures and retries; assert cost-per-outcome rises while spend looks flat | Done — [retry-storm-drill.md](./docs/validation/retry-storm-drill.md) |
| Context bloat | Pad context; show the waste as unit cost, not just total spend | Done — [context-bloat-drill.md](./docs/validation/context-bloat-drill.md) |
| Attribution accuracy | Reconcile attributed cost against the total; assert they agree | Done — [attribution-reconciliation-drill.md](./docs/validation/attribution-reconciliation-drill.md) |

**Exit criteria met, enforced by `make test` on every push, not just asserted in a report.** Each
drill is a real run against data `costkit` itself generated:

- **Cost regression** — `support-triage` silently moved onto a pricier model tier (token volume
  and failure rate unchanged) is caught by the anomaly detector at a >1.3x ratio.
- **Retry storm** — an 85% failure rate for `checkout-assistant` raises cost per outcome ~170%
  while hourly spend rises only ~116% — the exact "spend looks flat, unit cost doesn't" gap this
  repository exists to close, measured, not asserted.
- **Context bloat** — 5x input tokens for `doc-summarizer` raises cost per outcome with success
  rate staying >95%, proving the effect is real token waste, not a disguised retry storm.
- **Attribution reconciliation** — every stored event's cost reproduces exactly from its own
  stored tokens and price basis; the grand total agrees with the sum across every attribution
  slice. This is "reconciles with the bill" checked the only way possible without a real provider
  invoice — see [the drill's own disclosure](./docs/validation/attribution-reconciliation-drill.md)
  of that scope limit.

Full account, including why each drill's failure signature is distinct from the others, in
[docs/validation/README.md](./docs/validation/README.md).
